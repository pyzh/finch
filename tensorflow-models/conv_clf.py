import tensorflow as tf
import numpy as np
import math


class ConvClassifier:
    def __init__(self, img_h, img_w, n_out=2):
        self.img_h = img_h
        self.img_w = img_w
        self.n_out = n_out
        self.build_graph()
    # end constructor


    def build_graph(self):
        with tf.name_scope('input_layer'):
            self.add_input_layer()
        with tf.variable_scope('forward_path'):
            self.add_conv_layer(self.X, 'wc1', [5,5,1,32], 'bc1', [32])
            self.add_maxpool_layer(self.conv, k=2)
            self.add_conv_layer(self.conv, 'wc2', [5,5,32,64], 'bc2', [64])
            self.add_maxpool_layer(self.conv, k=2)
            self.add_fully_connected_layer(
                self.conv, self._W('wd1', [int(self.img_h/4)*int(self.img_w/4)*64, 1024]), self._b('bd1', [1024])
            )
        with tf.variable_scope('output_layer'):
            self.add_output_layer()   
        with tf.name_scope('backward_path'):
            self.add_backward_path()
        with tf.name_scope('session'):
            self.sess = tf.Session()
            self.init = tf.global_variables_initializer()
    # end method build_graph


    def add_input_layer(self):
        self.X = tf.placeholder(tf.float32, [None, self.img_h, self.img_w, 1])
        self.y = tf.placeholder(tf.float32, [None, self.n_out])
        self.keep_prob = tf.placeholder(tf.float32)
    # end method add_input_layer


    def add_conv_layer(self, in_layer, w_name, w_shape, b_name, b_shape):
        self.conv = self.conv2d(in_layer, self._W(w_name, w_shape), self._b(b_name, b_shape))
    # end method add_conv_layer


    def add_maxpool_layer(self, in_layer, k=2):
        self.conv = self.maxpool2d(in_layer, k=k)
    # end method add_maxpool_layer


    def add_fully_connected_layer(self, in_layer, W, b):
        fc = tf.reshape(in_layer, [-1, W.get_shape().as_list()[0]])
        fc = tf.nn.bias_add(tf.matmul(fc, W), b)
        fc = tf.nn.relu(fc)
        self.fc = tf.nn.dropout(fc, self.keep_prob)
    # end method fully_connected_layer


    def add_output_layer(self):
        self.logits = tf.nn.bias_add(tf.matmul(self.fc, self._W('w_out', [1024,self.n_out])),
                                     self._b('b_out', [self.n_out]))
    # end method add_output_layer


    def add_backward_path(self):
        self.lr = tf.placeholder(tf.float32)
        self.loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.logits, labels=self.y))
        self.train_op = tf.train.AdamOptimizer(self.lr).minimize(self.loss)
        self.acc = tf.reduce_mean(tf.cast(tf.equal(tf.argmax(self.logits, 1),tf.argmax(self.y, 1)), tf.float32))
    # end method add_backward_path


    def conv2d(self, X, W, b, strides=1):
        conv = tf.nn.conv2d(X, W, strides=[1, strides, strides, 1], padding='SAME')
        conv = tf.nn.bias_add(conv, b)
        return tf.nn.relu(conv)
    # end method conv2d


    def maxpool2d(self, X, k=2):
        return tf.nn.max_pool(X, ksize=[1, k, k, 1], strides=[1, k, k, 1], padding='SAME')
    # end method maxpool2d


    def _W(self, name, shape):
        return tf.get_variable(name, shape, tf.float32, tf.truncated_normal_initializer(stddev=0.1))
    # end method _W

    
    def _b(self, name, shape):
        return tf.get_variable(name, shape, tf.float32, tf.constant_initializer(0.1))
    # end method _b


    def fit(self, X, y, val_data=None, n_epoch=10, batch_size=128, keep_prob=0.5, en_exp_decay=True):
        if val_data is None:
            print("Train %d samples" % len(X))
        else:
            print("Train %d samples | Test %d samples" % (len(X), len(val_data[0])))
        log = {'loss':[], 'acc':[], 'val_loss':[], 'val_acc':[]}
        global_step = 0

        self.sess.run(self.init) # initialize all variables

        for epoch in range(n_epoch):
            # batch training
            local_step = 0
            for X_batch, y_batch in zip(self.gen_batch(X, batch_size), self.gen_batch(y, batch_size)):
                lr = self.adjust_lr(en_exp_decay, global_step, n_epoch, len(X), batch_size) 
                _, loss, acc = self.sess.run([self.train_op, self.loss, self.acc], feed_dict={self.X: X_batch,
                    self.y: y_batch, self.lr: lr, self.keep_prob: keep_prob})
                local_step += 1
                global_step += 1
                if (local_step + 1) % 100 == 0:
                    print ("Epoch %d/%d | Step %d/%d | train loss: %.4f | train acc: %.4f | lr: %.4f"
                           %(epoch+1, n_epoch, local_step+1, int(len(X)/batch_size), loss, acc, lr))
            if val_data is not None:
                # go through test dara, compute validation loss and acc
                val_loss_list, val_acc_list = [], []
                for X_test_batch, y_test_batch in zip(self.gen_batch(val_data[0], batch_size),
                                                      self.gen_batch(val_data[1], batch_size)):
                    v_loss, v_acc = self.sess.run([self.loss, self.acc], feed_dict={self.X: X_test_batch,
                        self.y: y_test_batch, self.keep_prob: 1.0})
                    val_loss_list.append(v_loss)
                    val_acc_list.append(v_acc)
                val_loss, val_acc = self.list_avg(val_loss_list), self.list_avg(val_acc_list)

            # append to log
            log['loss'].append(loss)
            log['acc'].append(acc)
            if val_data is not None:
                log['val_loss'].append(val_loss)
                log['val_acc'].append(val_acc)

            # verbose
            if val_data is None:
                print ("Epoch %d/%d | train loss: %.4f | train acc: %.4f |" % (epoch+1, n_epoch, loss, acc),
                       "lr: %.4f" % (lr) )
            else:
                print ("Epoch %d/%d | train loss: %.4f | train_acc: %.4f |" % (epoch+1, n_epoch, loss, acc),
                       "test loss: %.4f | test acc: %.4f |" % (val_loss, val_acc),
                       "lr: %.4f" % (lr) )
        return log
    # end method fit


    def predict(self, X_test, batch_size=128):
        batch_pred_list = []
        X_test_batch_list = np.array_split(X_test, int( len(X_test)/batch_size ))
        for X_test_batch in X_test_batch_list:
            batch_pred = self.sess.run(self.logits, feed_dict={self.X:X_test_batch, self.keep_prob:1.0})
            batch_pred_list.append(batch_pred)
        return np.concatenate(batch_pred_list)
    # end method predict


    def close(self):
        self.sess.close()
        tf.reset_default_graph()
    # end method close


    def gen_batch(self, arr, batch_size):
        if len(arr) % batch_size != 0:
            new_len = len(arr) - len(arr) % batch_size
            for i in range(0, new_len, batch_size):
                yield arr[i : i + batch_size]
        else:
            for i in range(0, len(arr), batch_size):
                yield arr[i : i + batch_size]
    # end method gen_batch


    def adjust_lr(self, en_exp_decay, global_step, n_epoch, len_X, batch_size):
        if en_exp_decay:
            max_lr = 0.003
            min_lr = 0.0001
            decay_rate = math.log(min_lr/max_lr) / (-n_epoch*len_X/batch_size)
            lr = max_lr*math.exp(-decay_rate*global_step)
        else:
            lr = 0.001
        return lr
    # end method adjust_lr


    def list_avg(self, l):
        return sum(l) / len(l)
    # end method list_avg
# end class LinearSVMClassifier
