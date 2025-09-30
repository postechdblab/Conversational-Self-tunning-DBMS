import torch
import torch.utils.data

from source.text2sql.ratsql.models import abstract_preproc
from source.text2sql.ratsql.utils import registry


class ZippedDataset(torch.utils.data.Dataset):
    def __init__(self, *components):
        assert len(components) >= 1
        lengths = [len(c) for c in components]
        assert all(
            lengths[0] == other for other in lengths[1:]
        ), f"Lengths don't match: {lengths}"
        self.components = components

    def __getitem__(self, idx):
        return tuple(c[idx] for c in self.components)

    def __len__(self):
        return len(self.components[0])


@registry.register("model", "EncDec")
class EncDecModel(torch.nn.Module):
    class Preproc(abstract_preproc.AbstractPreproc):
        def __init__(self, encoder, decoder, encoder_preproc, decoder_preproc):
            super().__init__()

            self.enc_preproc = registry.lookup("encoder", encoder["name"]).Preproc(
                **encoder_preproc
            )
            self.dec_preproc = registry.lookup("decoder", decoder["name"]).Preproc(
                **decoder_preproc
            )

        def validate_item(self, item, section):
            bert_version = (
                self.enc_preproc.bert_version
                if hasattr(self.enc_preproc, "bert_version")
                else None
            )
            enc_result, enc_info = self.enc_preproc.validate_item(
                item, section, bert_version=bert_version
            )
            dec_result, dec_info = self.dec_preproc.validate_item(item, section)

            return enc_result and dec_result, (enc_info, dec_info)

        def add_item(self, item, section, validation_info, manual_linking_info=None):
            enc_info, dec_info = validation_info
            bert_version = (
                self.enc_preproc.bert_version
                if hasattr(self.enc_preproc, "bert_version")
                else None
            )
            is_added, enc_preproc_item = self.enc_preproc.add_item(
                item,
                section,
                enc_info,
                bert_version=bert_version,
                manual_linking_info=manual_linking_info,
            )
            if is_added or section in {"aux"}:
                dec_preproc_item = self.dec_preproc.add_item(item, section, dec_info)
            return is_added, (enc_preproc_item, dec_preproc_item)

        def add_item_from_cache(self, cached_item, section):
            enc_preproc_item, dec_preproc_item = cached_item
            self.enc_preproc.add_item_from_cache(enc_preproc_item, section)
            self.dec_preproc.add_item_from_cache(dec_preproc_item, section)

        def clear_items(self):
            self.enc_preproc.clear_items()
            self.dec_preproc.clear_items()

        def save(self, is_inference=False):
            self.enc_preproc.save(is_inference)
            self.dec_preproc.save(is_inference)

        def load(self, checkpoint_path=None):
            self.enc_preproc.load()
            self.dec_preproc.load(checkpoint_path=checkpoint_path)

        def dataset(self, section):
            return ZippedDataset(
                self.enc_preproc.dataset(section), self.dec_preproc.dataset(section)
            )

    def __init__(self, preproc, device, encoder, decoder):
        super().__init__()
        self.preproc = preproc
        self.encoder = registry.construct(
            "encoder", encoder, device=device, preproc=preproc.enc_preproc
        )
        self.decoder = registry.construct(
            "decoder", decoder, device=device, preproc=preproc.dec_preproc
        )

        if getattr(self.encoder, "batched"):
            if "cosql" in encoder["name"]:
                self.compute_loss = self._compute_loss_enc_batched_cosql
            else:
                self.compute_loss = self._compute_loss_enc_batched
        else:
            self.compute_loss = self._compute_loss_unbatched

    def forward(self, *args, **kwargs):
        return self.compute_loss(*args, **kwargs)

    def _compute_loss_enc_batched(self, batch, debug=False, with_acc=False):
        losses = []
        results = []
        enc_states = self.encoder(
            [enc_input for enc_input, dec_output in batch], debug=debug
        )

        for enc_state, (enc_input, dec_output) in zip(enc_states, batch):
            result = self.decoder.compute_loss(enc_input, dec_output, enc_state, debug)
            if debug:
                results.append(tuple((result[0], result[1], enc_state.return_dic)))
            else:
                losses.append(result)
        if debug:
            return results
        else:
            return torch.mean(torch.stack(losses, dim=0), dim=0)

    def _compute_loss_enc_batched_cosql(self, batch, debug=False, with_acc=False):
        enc_states = self.encoder(
            [enc_input for enc_input, dec_output in batch], debug=debug
        )
        losses = self.decoder.compute_loss(batch, enc_states)
        return losses

    def _compute_loss_enc_batched2(self, batch, debug=False):
        losses = []
        for enc_input, dec_output in batch:
            (enc_state,) = self.encoder([enc_input])
            loss = self.decoder.compute_loss(enc_input, dec_output, enc_state, debug)
            losses.append(loss)
        if debug:
            return losses
        else:
            return torch.mean(torch.stack(losses, dim=0), dim=0)

    def _compute_loss_unbatched(self, batch, debug=False, with_acc=False):
        losses = []
        accs = []
        for enc_input, dec_output in batch:
            enc_state = self.encoder(enc_input)
            loss, acc = self.decoder.compute_loss(
                enc_input, dec_output, enc_state, debug, with_acc
            )
            losses.append(loss)
            accs.append(acc)
        if debug:
            return losses
        else:
            return torch.mean(torch.stack(losses, dim=0), dim=0), accs

    def eval_on_batch(self, batch):
        mean_loss, acc = self.compute_loss(batch, False, True)
        mean_loss = mean_loss.item()
        batch_size = len(batch)
        result = {"loss": mean_loss * batch_size, "total": batch_size}
        return result, acc

    def begin_inference(self, orig_item, preproc_item):
        enc_input, _ = preproc_item
        if getattr(self.encoder, "batched"):
            (enc_state,) = self.encoder([enc_input])
        else:
            enc_state = self.encoder(enc_input)
        return self.decoder.begin_inference(enc_state, orig_item)

    def begin_inference_captum(
        self, orig_item, preproc_item, input, att_masks, tok_type_lists
    ):
        enc_input, _ = preproc_item
        decode_traversal = []
        decode_choices = []
        if getattr(self.encoder, "batched"):
            enc_state = self.encoder(
                [enc_input] * len(input), input, att_masks, tok_type_lists
            )
        else:
            enc_state = self.encoder(enc_input)
        for i in range(len(input)):
            traversal, choices = self.decoder.begin_inference(enc_state[i], orig_item)
            decode_traversal.append(traversal)
            decode_choices.append(choices)
        return decode_traversal, decode_choices  # traversal, choices를 return할 것이다.
