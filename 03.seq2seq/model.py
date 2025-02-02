import tensorflow as tf

class seq2seq:

    def __init__(self, sess, encoder_vocab_size, decoder_vocab_size, max_step=50,
                 embedding_size=300, encoder_hidden_size=128):
        self.sess = sess
        self.encoder_vocab_size = encoder_vocab_size
        self.decoder_vocab_size = decoder_vocab_size
        self.max_step = max_step
        self.embedding_size = embedding_size
        self.encoder_hidden_size = encoder_hidden_size
        self.decoder_hidden_size = encoder_hidden_size * 2
        self._build_net()

    def _build_net(self):
        self.encoder_inputs = tf.placeholder(dtype=tf.int32, shape=(None, None), name='encoder_inputs')
        encoder_inputs_length = tf.reduce_sum(tf.sign(self.encoder_inputs), axis=1)
        self.embedding = tf.get_variable('embedding', dtype=tf.float32,
                                         initializer=tf.random_uniform((self.encoder_vocab_size, self.embedding_size), minval=-1.0, maxval=1.0))
        self.decoder_targets = tf.placeholder(dtype=tf.int32, shape=(None, None), name='decoder_inputs')
        decoder_targets_length = tf.reduce_sum(tf.sign(self.decoder_targets), axis=1) + 1
        batch_size, decoder_max_length = tf.unstack(tf.shape(self.decoder_targets))
        decoder_inputs = tf.concat((tf.transpose([tf.ones([batch_size], dtype=tf.int32)], perm=(1,0)), self.decoder_targets[:,:-1]), axis=1)
        self.encoder_fw_cell = tf.nn.rnn_cell.LSTMCell(self.encoder_hidden_size)
        self.encoder_bw_cell = tf.nn.rnn_cell.LSTMCell(self.encoder_hidden_size)
        self.decoder_cell = tf.nn.rnn_cell.LSTMCell(self.decoder_hidden_size)
        embedded_encoder_inputs = tf.nn.embedding_lookup(self.embedding, self.encoder_inputs)
        embedded_decoder_inputs = tf.nn.embedding_lookup(self.embedding, decoder_inputs)
        ((_, _),
         (encoder_fw_last_state, encoder_bw_last_state)) = tf.nn.bidirectional_dynamic_rnn(self.encoder_fw_cell,
                                                                                           self.encoder_bw_cell,
                                                                                           embedded_encoder_inputs,
                                                                                           encoder_inputs_length,
                                                                                           dtype=tf.float32)

        encoder_final_state_c = tf.concat((encoder_fw_last_state.c, encoder_bw_last_state.c), 1)
        encoder_final_state_h = tf.concat((encoder_fw_last_state.h, encoder_bw_last_state.h), 1)
        self.encoder_final_state = tf.nn.rnn_cell.LSTMStateTuple(encoder_final_state_c, encoder_final_state_h)

        decoder_output, decoder_last_state = tf.nn.dynamic_rnn(self.decoder_cell,
                                                               embedded_decoder_inputs,
                                                               initial_state=self.encoder_final_state)

        self.W = tf.get_variable('W', initializer=tf.truncated_normal(shape=(self.decoder_hidden_size, self.decoder_vocab_size)))
        self.b = tf.get_variable('b', initializer=tf.constant(0.1, shape=(self.decoder_vocab_size,)))

        batch_size, max_time_step = tf.unstack(tf.shape(self.decoder_targets))
        decoder_output = tf.reshape(decoder_output, [-1, self.decoder_hidden_size]) # [batch_size*time_step, decoder_hidden_size]
        logits = tf.add(tf.matmul(decoder_output, self.W), self.b) #
        logits = tf.reshape(logits, [batch_size, max_time_step, -1])
        self.loss = tf.reduce_mean(tf.contrib.seq2seq.sequence_loss(logits=logits,
                                                                    targets=self.decoder_targets,
                                                                    weights=tf.sequence_mask(decoder_targets_length, decoder_max_length,
                                                                    dtype=tf.float32)))
        global_step = tf.Variable(0, trainable=False)
        starter_learning_rate = 0.1
        learning_rate = tf.train.exponential_decay(starter_learning_rate, global_step,
                                                   1e+3, 0.96, staircase=True)
        optimizer = tf.train.AdamOptimizer(learning_rate)
        gvs = optimizer.compute_gradients(self.loss)
        capped_gvs = [(tf.clip_by_value(grad, -1., 1.), var) for grad, var in gvs]
        self.train_op = optimizer.apply_gradients(capped_gvs, global_step=global_step)
        batch_size = tf.unstack(tf.shape(self.encoder_inputs))[0]
        go_time_slice = tf.ones([batch_size], dtype=tf.int32, name='GO')
        self.predictions = []
        prediction = None
        state = self.encoder_final_state
        for i in range(self.max_step):
            if i == 0:
                input_ = tf.nn.embedding_lookup(self.embedding, go_time_slice)
            else:
                input_ = tf.nn.embedding_lookup(self.embedding, prediction)

            output, state = self.decoder_cell(input_, state)
            logits = tf.add(tf.matmul(output, self.W), self.b)
            prediction = tf.argmax(logits, 1)
            self.predictions.append(prediction)
        self.predictions = tf.stack(self.predictions, 1)

    def train(self, encoder_inputs, decoder_targets):
        return self.sess.run([self.loss, self.train_op], feed_dict={self.encoder_inputs:encoder_inputs, self.decoder_targets:decoder_targets})

    def inference(self, encoder_inputs):
        return self.sess.run(self.predictions, feed_dict={self.encoder_inputs: encoder_inputs})

    def setMaxStep(self, max_step):
        self.max_step = max_step