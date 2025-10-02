import torch
import json
from source.text2sql.ratsql.utils import registry
from captum.attr import LayerIntegratedGradients, visualization
from source.text2sql.ratsql.models.spider import spider_beam_search
from source.text2sql.ratsql.models.spider.spider_enc import SpiderEncoderBertPreproc


class Attribution:
    def __init__(self, config):
        self.config = config
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")
            torch.set_num_threads(1)
        # 0. Construct preprocessors
        self.model_preproc = SpiderEncoderBertPreproc(
            **config["model"]["encoder_preproc"]
        )
        self.vis_data_records_ig = []
        self.tokenizer = self.model_preproc.tokenizer

    def pad_sequence_for_bert_batch(self, tokens_lists):
        pad_id = self.tokenizer.pad_token_id
        max_len = max([len(it) for it in tokens_lists])
        assert max_len <= 512
        toks_ids = []
        att_masks = []
        tok_type_lists = []
        for item_toks in tokens_lists:
            padded_item_toks = item_toks + [pad_id] * (max_len - len(item_toks))
            toks_ids.append(padded_item_toks)

            _att_mask = [1] * len(item_toks) + [0] * (max_len - len(item_toks))
            att_masks.append(_att_mask)

            first_sep_id = padded_item_toks.index(self.tokenizer.sep_token_id)
            assert first_sep_id > 0
            _tok_type_list = [0] * (first_sep_id + 1) + [1] * (
                max_len - first_sep_id - 1
            )
            tok_type_lists.append(_tok_type_list)
        return toks_ids, att_masks, tok_type_lists

    def preprocess(self, model, preproc_item, token_question):
        batch_token_lists = []
        # padding at token question
        qs = self.pad_single_sentence_for_bert(token_question, cls=True, model=model)
        cols = [
            self.pad_single_sentence_for_bert(c, cls=False, model=model)
            for c in preproc_item["columns"]
        ]
        tabs = [
            self.pad_single_sentence_for_bert(t, cls=False, model=model)
            for t in preproc_item["tables"]
        ]
        # make total token list
        token_list = (
            qs + [c for col in cols for c in col] + [t for tab in tabs for t in tab]
        )
        # convert tokens to ids
        indexed_token_list = self.tokenizer.convert_tokens_to_ids(token_list)
        batch_token_lists.append(indexed_token_list)
        # add pad on token list and produce attantion mask/token type list
        (
            padded_token_lists,
            att_mask_lists,
            tok_type_lists,
        ) = self.pad_sequence_for_bert_batch(batch_token_lists)
        tokens_tensor = torch.LongTensor(padded_token_lists).to(self.device)
        att_masks_tensor = torch.LongTensor(att_mask_lists).to(self.device)
        tok_type_tensor = torch.LongTensor(tok_type_lists).to(self.device)
        return tokens_tensor, att_masks_tensor, tok_type_tensor

    def pad_single_sentence_for_bert(self, toks, cls=True, model=None):
        if cls:
            return (
                [model.preproc.enc_preproc.tokenizer.cls_token]
                + toks
                + [model.preproc.enc_preproc.tokenizer.sep_token]
            )
        else:
            return toks + [model.preproc.enc_preproc.tokenizer.sep_token]

    def forward_func_for_ig(
        self,
        inputs,
        model,
        orig_item,
        preproc_item,
        beam_size,
        att_masks,
        tok_type_lists,
        token_question,
        question,
        col_index=None,
        col_att=None,
    ):
        score_list = []
        preproc_item["question"] = self.tokenizer.convert_ids_to_tokens(inputs[0])[
            1 : len(token_question) + 1
        ]
        preproc_item["raw_question"] = question
        orig_item.text = self.tokenizer.convert_ids_to_tokens(inputs[0])[
            1 : len(token_question) + 1
        ]
        beams_model = spider_beam_search.beam_search_with_captum(
            inputs,
            model,
            orig_item,
            (preproc_item, None),
            beam_size=beam_size,
            max_steps=1000,
            from_cond=False,
            att_masks=att_masks,
            tok_type_lists=tok_type_lists,
        )
        if col_att:
            for i in range(len(inputs)):
                try:
                    score_list.append(
                        beams_model[i][0].score_history[col_index].unsqueeze(0)
                    )
                except:
                    print("error")
            return torch.stack(score_list, dim=0).squeeze(1)
        else:
            for i in range(len(inputs)):
                score_list.append(beams_model[i][0].score.unsqueeze(0))
            return torch.stack(score_list, dim=0).squeeze(1)

    def post_process(
        self,
        token_question,
        predict_answer,
        inffered_answer,
        score,
        attributions_ig_list,
        delta_list,
        indicies,
        col_name_list,
    ):
        # summarize attributions of each input tokens
        attribution_only_question_list = []
        attributions_with_schema_list = []
        for attributions_ig, delta in zip(attributions_ig_list, delta_list):
            attributions_only_question = self.add_attributions_to_visualizer(
                attributions_ig[0][1 : len(token_question) + 1].unsqueeze(0),
                token_question,
                score,
                delta,
                self.vis_data_records_ig,
            )
            attributions_with_schema = self.add_attributions_to_visualizer(
                attributions_ig[0].unsqueeze(0),
                self.tokenizer.convert_ids_to_tokens(indicies[0]),
                score,
                delta,
                self.vis_data_records_ig,
            )
            attribution_only_question_list.append(attributions_only_question)
            attributions_with_schema_list.append(attributions_with_schema)
        return (
            attribution_only_question_list,
            attributions_with_schema_list,
            delta_list,
            score,
            indicies,
            len(token_question),
            predict_answer,
            inffered_answer,
            col_name_list,
        )

    def add_attributions_to_visualizer(
        self, attributions, text, pred, delta, vis_data_records
    ):
        attributions = attributions.sum(dim=-1).squeeze(0)
        attributions = attributions / torch.norm(attributions)
        attributions = attributions.cpu().detach().numpy()
        label_vocab = {0: "wrong", 1: "correct"}
        vis_data_records.append(
            visualization.VisualizationDataRecord(
                attributions,
                pred,
                label_vocab[1],
                label_vocab[1],
                label_vocab[1],
                attributions.sum(),
                text,
                delta,
            )
        )
        return attributions

    def get_html(
        self,
        attributions_only_question_list,
        attributions_with_schema_list,
        delta_list,
        scores,
        indicies,
        len_q,
        predict_answer,
        inffered_answer,
        col_name_list,
    ):
        output_path = "./analysis_result.al"
        output = open(output_path, "w")
        for (
            attributions_only_question,
            attributions_with_schema,
            delta,
            col_name,
        ) in zip(
            attributions_only_question_list,
            attributions_with_schema_list,
            delta_list,
            col_name_list,
        ):
            output.write(
                json.dumps(
                    {
                        "question": self.tokenizer.convert_ids_to_tokens(indicies[0])[
                            1 : len_q + 1
                        ],
                        "inffered_answer": inffered_answer,
                        "predict_tok_seq_answer": predict_answer,
                        "full input": self.tokenizer.convert_ids_to_tokens(indicies[0]),
                        "col_name": col_name,
                        "attributions_only_question": attributions_only_question.tolist(),
                        "attributions_with_schema": attributions_with_schema.tolist(),
                        "delta": delta.cpu().detach().numpy().tolist(),
                        "scores": scores.cpu().detach().numpy().tolist(),
                    }
                )
                + "\n"
            )
            output.flush()
        html = visualization.visualize_text(self.vis_data_records_ig)
        html_path = output_path + ".html"
        html_output = open(html_path, "w")
        html_output.write(html.data)
        return output_path

    def get_analysis_result(self, attributions, text, pred, delta):
        attributions = attributions.sum(dim=-1).squeeze(0)
        attributions = attributions / torch.norm(attributions)
        attributions = attributions.cpu().detach().numpy()
        label_vocab = {0: "wrong", 1: "correct"}
        pred_label = label_vocab[1]
        true_label = label_vocab[1]
        analysis_result = visualization.VisualizationDataRecord(
            attributions,
            pred,
            pred_label,
            true_label,
            pred_label,
            attributions.sum(),
            text,
            delta,
        )
        raw_input = analysis_result.raw_input_ids
        word_attributions = analysis_result.word_attributions
        return raw_input, word_attributions

    def run(self, model, question, orig_item, preproc_item, col_att=True):
        beam_size = 1
        # sequence of question's token
        token_question = self.tokenizer.tokenize(question)
        # preprocess data for making input of BERT encoder(seq of word_tokens -> seq of token_ids)
        input_indices_tensor, att_masks, tok_type_lists = self.preprocess(
            model, preproc_item, token_question
        )
        # make reference input of BERT encoder for integratedGradients
        ref_indices_tensor = torch.zeros_like(input_indices_tensor).to(self.device)
        # normal score from beam search
        score_list = spider_beam_search.beam_search_with_captum(
            input_indices_tensor,
            model,
            orig_item,
            (preproc_item, None),
            beam_size=beam_size,
            max_steps=1000,
            from_cond=False,
            att_masks=att_masks,
            tok_type_lists=tok_type_lists,
        )
        score = score_list[0][0].score
        _, inferred_answer = score_list[0][0].inference_state.finalize()
        predict_answer = score_list[0][0].choice_history
        # get attribution results via LayerIntergratedGradients
        lig = LayerIntegratedGradients(
            self.forward_func_for_ig, model.encoder.bert_model.embeddings
        )
        col_attribution = []
        col_delta = []
        col_name = []
        if col_att:
            i = 0
            for col_index in score_list[0][0].column_index:
                attributions_ig, delta = lig.attribute(
                    inputs=input_indices_tensor,
                    baselines=ref_indices_tensor,
                    n_steps=50,
                    additional_forward_args=(
                        model,
                        orig_item,
                        preproc_item,
                        beam_size,
                        att_masks,
                        tok_type_lists,
                        token_question,
                        question,
                        col_index,
                        col_att,
                    ),
                    return_convergence_delta=True,
                )
                col_attribution.append(attributions_ig)
                col_delta.append(delta)
                col_name.append(
                    preproc_item["columns"][score_list[0][0].column_history[i]]
                )
                i += 1
            attributions_ig_list = col_attribution
            delta_list = col_delta
        else:
            attributions_ig, delta = lig.attribute(
                inputs=input_indices_tensor,
                baselines=ref_indices_tensor,
                n_steps=50,
                additional_forward_args=(
                    model,
                    orig_item,
                    preproc_item,
                    beam_size,
                    att_masks,
                    tok_type_lists,
                    token_question,
                    question,
                ),
                return_convergence_delta=True,
            )
            attributions_ig_list = [attributions_ig]
            delta_list = [delta]

        raw_input, word_attributions = self.get_analysis_result(
            attributions_ig_list[0][0][1 : len(token_question) + 1].unsqueeze(0),
            token_question,
            score,
            delta[0],
        )
        return raw_input, word_attributions.tolist()
