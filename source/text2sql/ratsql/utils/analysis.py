import torch


def cal_attention_flow(att_mat, do_softmax=False):    
    ## Input: att_mat :: shape(layer_num, head_num, input_len, input_len)
    ## Output: join_weight_matrix :: shape(input_len, input_len)
    
    # Average the attention weights across all heads
    att_mat = torch.mean(att_mat, dim=1)

    # Add an identity matrix to account for residual connections
    residual_att = torch.eye(att_mat.size(1), device=att_mat.device)
    aug_att_mat = residual_att + att_mat

    # Re-normalize the weights
    aug_att_mat = aug_att_mat / aug_att_mat.sum(dim=-1).unsqueeze(-1)

    # Recursively multiply the weight matrices
    joint_attention_list = [aug_att_mat[0]]
    for idx in range(1, aug_att_mat.size(0)):
        joint_attention_list.append(joint_attention_list[idx-1] * aug_att_mat[idx])

    # Visuzlize the attention
    joint_weight_matrix = joint_attention_list[-1]

    if do_softmax:
        return torch.nn.functional.softmax(joint_weight_matrix, dim=-1)
    else:
        return joint_weight_matrix


if __name__ == "__main__":
    tmp_tensor = torch.randn(12, 6, 4, 4)
    attention_weight_matrix = cal_attention_flow(tmp_tensor)
