"""
         __  _ __
  __  __/ /_(_) /
 / / / / __/ / /
/ /_/ / /_/ / /
\__,_/\__/_/_/ v0.2
Making useful stuff happen since 2016
"""

import tensorflow as tf


def get_by_index(tensor, index):
    """
    :param tensor: [dim1 x dim2 x dim3] tensor
    :param index: [dim1] tensor of indices for dim2
    :return: [dim1 x dim3] tensor
    """
    dim1, dim2, dim3 = tf.unstack(tf.shape(tensor))
    flat_index = tf.range(0, dim1) * dim2 + (index - 1)
    return tf.gather(tf.reshape(tensor, [-1, dim3]), flat_index)


def get_last(tensor):
    """
    :param tensor: [dim1 x dim2 x dim3] tensor
    :return: [dim1 x dim3] tensor
    """
    shape = tf.shape(tensor)  # [dim1, dim2, dim3]
    slice_size = shape * [1, 0, 1] + [0, 1, 0]  # [dim1, 1 , dim3]
    slice_begin = shape * [0, 1, 0] + [0, -1, 0]  # [1, dim2-1, 1]
    return tf.squeeze(tf.slice(tensor, slice_begin, slice_size), [1])


def mask_for_lengths(lengths, batch_size=None, max_length=None, mask_right=True,
                     value=-1000.0):
    """
    Creates a [batch_size x max_length] mask.
    :param lengths: int64 1-dim tensor of batch_size lengths
    :param batch_size: int32 0-dim tensor or python int
    :param max_length: int32 0-dim tensor or python int
    :param mask_right: if True, everything before "lengths" becomes zero and the
        rest "value", else vice versa
    :param value: value for the mask
    :return: [batch_size x max_length] mask of zeros and "value"s
    """
    if max_length is None:
        max_length = tf.cast(tf.reduce_max(lengths), tf.int32)
    if batch_size is None:
        batch_size = tf.shape(lengths)[0]
    # [batch_size x max_length]
    mask = tf.reshape(tf.tile(tf.range(0, max_length), [batch_size]), tf.stack([batch_size, -1]))
    if mask_right:
        mask = tf.greater_equal(tf.cast(mask, tf.int64), tf.expand_dims(lengths, 1))
    else:
        mask = tf.less(tf.cast(mask, tf.int64), tf.expand_dims(lengths, 1))
    mask = tf.cast(mask, tf.float32) * value
    return mask


def tfrun(tensor):
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        return sess.run(tensor)


def tfrunprint(tensor, suffix="", prefix=""):
    if prefix == "":
        print(tfrun(tensor), suffix)
    else:
        print(prefix, tfrun(tensor), suffix)


def tfrunprintshape(tensor, suffix="", prefix=""):
    tfrunprint(tf.shape(tensor), suffix, prefix)


def tfprint(tensor, fun=None, prefix=""):
    if fun is None:
        fun = lambda x: x
    return tf.Print(tensor, [fun(tensor)], prefix)


def tfprints(tensors, fun=None, prefix=""):
    if fun is None:
        fun = lambda x: x
    prints = []
    for i in range(0, len(tensors)):
        prints.append(tf.Print(tensors[i], [fun(tensors[i])], prefix))
    return prints


def tfprintshapes(tensors, prefix=""):
    return tfprints(tensors, lambda x: tf.shape(x), prefix)


def tfprintshape(tensor, prefix=""):
    return tfprint(tensor, lambda x: tf.shape(x), prefix)


def gather_in_dim(params, indices, dim, name=None):
    """
    Gathers slices in a defined dimension. If dim == 0 this is doing the same
      thing as tf.gather.
    """
    if dim == 0:
        return tf.gather(params, indices, name)
    else:
        dims = [i for i in range(0, len(params.get_shape()))]
        to_dims = list(dims)
        to_dims[0] = dim
        to_dims[dim] = 0

        transposed = tf.transpose(params, to_dims)
        gathered = tf.gather(transposed, indices)
        reverted = tf.transpose(gathered, to_dims)

        return reverted


def unit_length(tensor):
    l2norm_sq = tf.reduce_sum(tensor * tensor, 1, keep_dims=True)
    l2norm = tf.rsqrt(l2norm_sq)
    return tensor * l2norm


def segment_softmax(scores, partition):
    """Given scores and a partition, converts scores to probs by performing
    softmax over all rows within a partition."""

    # Subtract max
    max_per_partition = tf.segment_max(tf.reduce_max(scores, axis=1), partition)
    scores -= tf.expand_dims(tf.gather(max_per_partition, partition), axis=1)

    # Compute probs
    scores_exp = tf.exp(scores)
    scores_exp_sum_per_partition = tf.segment_sum(tf.reduce_sum(scores_exp, axis=1), partition)
    probs = scores_exp / tf.expand_dims(tf.gather(scores_exp_sum_per_partition, partition), axis=1)

    return probs


def segment_argmax(input, partition):
    """Computes row and col indices Tensors of the segment max in the 2D input."""

    with tf.name_scope("segment_argmax"):

        num_partitions = tf.reduce_max(partition) + 1

        def segment_is_max(i, p):
            max_per_partition = tf.segment_max(tf.reduce_max(i, axis=1), p)
            return tf.equal(i, tf.expand_dims(tf.gather(max_per_partition, p), 1))

        is_max = segment_is_max(input, partition)

        # The current is_max could still contain multiple True entries per
        # partition. As long as they are in the same row, that is not a problem.
        # However, we do need to remove duplicate Trues in the same partition
        # in multiple rows.
        # For that, we'll multiply is_max with the row indices + 1 and perform
        # segment_is_max() again.

        rows = tf.shape(input)[0]
        cols = tf.shape(input)[1]
        row_indices = tf.tile(tf.expand_dims(tf.range(rows), 1), [1, cols])
        is_max = segment_is_max(tf.cast(is_max, tf.int32) * (row_indices + 1), partition)

        # Get selected rows and columns
        row_selected = tf.reduce_any(is_max, axis=1)
        row_indices = tf.squeeze(tf.where(row_selected))
        rows_selected = tf.reduce_sum(tf.cast(row_selected, tf.int64))

        # Assert rows_selected is correct & ensure row_indices is always 1D
        with tf.control_dependencies([tf.assert_equal(rows_selected, num_partitions)]):
            row_indices = tf.reshape(row_indices, [-1])

        selected_rows_is_max = tf.gather(is_max, row_indices)
        col_indices = tf.argmax(tf.cast(selected_rows_is_max, tf.int64), axis=1)

        # Pack indices
        return row_indices, col_indices


def gather_rowwise_indices_1d(indices):
    """Transforms 1D indices tensor to _indices such that:
    tf.gather_nd(some_2d_tensor, _indices) is equivalent to:
         rows = [tf.gather(some_2d_tensor[i], indices[i]) for i in range(n_rows)]
         result = tf.pack(rows)
    """

    rows = tf.shape(indices)[0]

    # Compute [rows, 2] indices tensor of [row_index, col_index] entries
    row_index = tf.cast(tf.range(rows), tf.int64)
    _indices = tf.transpose(tf.stack([row_index, indices]))

    return _indices


def gather_rowwise_indices_2d(indices):
    """Transforms 2D indices tensor to _indices such that:
    tf.gather_nd(some_2d_tensor, _indices) is equivalent to:
         rows = [tf.gather(some_2d_tensor[i], indices[i]) for i in range(n_rows)]
         result = tf.pack(rows)
    """

    rows = tf.shape(indices)[0]
    cols = tf.shape(indices)[1]

    # Compute [rows, cols, 2] indices tensor of [row_index, col_index] entries
    row_index = tf.expand_dims(tf.range(rows), 1)
    row_index_tiled = tf.tile(row_index, tf.stack([1, cols]))
    _indices = tf.stack([row_index_tiled, indices])
    _indices = tf.transpose(_indices, [1, 2, 0])

    return _indices


def gather_rowwise_1d(input, indices):

    with tf.name_scope("gather_rowwise_nd"):
        return tf.gather_nd(input,
                            tf.cast(gather_rowwise_indices_1d(indices),
                                    tf.int32))


def gather_rowwise_2d(input, indices):

    return tf.gather_nd(input, gather_rowwise_indices_2d(indices))


def fused_rnn_backward(fused_rnn, inputs, sequence_length, initial_state=None, dtype=None, scope=None, time_major=True):
    if not time_major:
        inputs = tf.transpose(inputs, [1, 0, 2])
    #assumes that time dim is 0 and batch is 1
    rev_inputs = tf.reverse_sequence(inputs, sequence_length, 0, 1)
    rev_outputs, last_state = fused_rnn(rev_inputs, sequence_length=sequence_length, initial_state=initial_state,
                                        dtype=dtype, scope=scope)
    outputs = tf.reverse_sequence(rev_outputs, sequence_length, 0, 1)
    if not time_major:
        outputs = tf.transpose(outputs, [1, 0, 2])
    return outputs, last_state


def fused_birnn(fused_rnn, inputs, sequence_length, initial_state=None, dtype=None, scope=None, time_major=True,
                backward_device=None):
    with tf.variable_scope(scope or "BiRNN"):
        sequence_length = tf.cast(sequence_length, tf.int32)
        if not time_major:
            inputs = tf.transpose(inputs, [1, 0, 2])
        outputs_fw, state_fw = fused_rnn(inputs, sequence_length=sequence_length, initial_state=initial_state,
                                         dtype=dtype, scope="FW")

        if backward_device is not None:
            with tf.device(backward_device):
                outputs_bw, state_bw = fused_rnn_backward(fused_rnn, inputs, sequence_length, initial_state, dtype, scope="BW")
        else:
            outputs_bw, state_bw = fused_rnn_backward(fused_rnn, inputs, sequence_length, initial_state, dtype, scope="BW")

        if not time_major:
            outputs_fw = tf.transpose(outputs_fw, [1, 0, 2])
            outputs_bw = tf.transpose(outputs_bw, [1, 0, 2])
    return (outputs_fw, outputs_bw), (state_fw, state_bw)
