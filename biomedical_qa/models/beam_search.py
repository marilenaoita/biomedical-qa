import tensorflow as tf

class BeamSearchDecoder(object):


    def __init__(self, beam_size, answer_partition):

        self._beam_size = beam_size
        self._answer_partition = answer_partition


    def receive_start_scores(self, start_scores):

        self._start_scores = tf.gather(start_scores, self._answer_partition)

        start_probs = tf.nn.softmax(start_scores)
        start_probs = tf.gather(start_probs, self._answer_partition)
        top_start_probs, top_starts = tf.nn.top_k(start_probs, self._beam_size)

        self._top_start_probs = tf.reshape(top_start_probs, [-1])
        self._top_starts = tf.cast(tf.reshape(top_starts, [-1]), tf.int64)

        return self._top_starts


    def receive_end_scores(self, end_scores):

        self._end_scores = end_scores

        end_probs = tf.nn.softmax(end_scores)
        top_end_probs, top_ends = tf.nn.top_k(end_probs, 1)

        self._top_end_probs = tf.reshape(top_end_probs, [-1])
        self._top_ends = tf.cast(tf.reshape(top_ends, [-1]), tf.int64)


    def get_top_spans(self):
        """Returns the top <beam size> starts with their most likely end."""

        # Reshape
        top_starts = tf.reshape(self._top_starts, [-1, self._beam_size])
        top_ends = tf.reshape(self._top_ends, [-1, self._beam_size])

        # Sort according to probability
        total_probs = self._top_start_probs * self._top_end_probs
        total_probs = tf.reshape(total_probs, [-1, self._beam_size])
        _, col_indices = tf.nn.top_k(total_probs, self._beam_size, sorted=True)

        rows = tf.shape(col_indices)[0]
        row_index = tf.reshape(tf.range(rows), tf.pack([rows, 1]))
        row_index_tiled = tf.tile(row_index, tf.pack([1, self._beam_size]))
        indices = tf.pack([row_index_tiled, col_indices])
        indices = tf.transpose(indices, [1, 2, 0])

        sorted_top_starts = tf.gather_nd(top_starts, indices)
        sorted_top_ends = tf.gather_nd(top_ends, indices)

        return sorted_top_starts, sorted_top_ends


    def get_final_prediction(self):

        n_candidates = tf.shape(self._top_end_probs)[0]
        total_probs = self._top_start_probs * self._top_end_probs
        total_probs = tf.reshape(total_probs, [-1, self._beam_size])

        segment_indices = tf.arg_max(total_probs, 1)
        offsets = tf.cast(tf.range(0, n_candidates, self._beam_size), tf.int64)
        indices = segment_indices + offsets

        start_scores = self._start_scores
        end_scores = tf.gather(self._end_scores, indices)
        starts = tf.gather(self._top_starts, indices)
        ends = tf.gather(self._top_ends, indices)

        return start_scores, end_scores, starts, ends


    def get_beam_search_partition(self, partitions):
        """Compute partition indices, which each index repeated <beam_size> times."""

        indices = tf.range(partitions)
        indices = tf.reshape(indices, [-1, 1])
        indices = tf.tile(indices, tf.pack([1, self._beam_size]))
        indices = tf.reshape(indices, [-1])

        return indices


    def expand_batch(self, tensor):

        partitions = tf.shape(tensor)[0]
        indices = self.get_beam_search_partition(partitions)
        return tf.gather(tensor, indices)
