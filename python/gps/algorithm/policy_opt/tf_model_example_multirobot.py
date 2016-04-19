""" This file provides an example tensorflow network used to define a policy. """

import tensorflow as tf
from gps.algorithm.policy_opt.tf_utils import TfMap
import numpy as np


def init_weights_shared(shape, name=None):
    weights = tf.get_variable("weights" + str(name), shape,
        initializer=tf.random_normal_initializer())
    return weights

def get_xavier_weights_shared(filter_shape, poolsize=(2, 2), name=None):
    fan_in = np.prod(filter_shape[1:])
    fan_out = (filter_shape[0] * np.prod(filter_shape[2:]) //
               np.prod(poolsize))
    low = -4*np.sqrt(6.0/(fan_in + fan_out)) # use 4 for sigmoid, 1 for tanh activation
    high = 4*np.sqrt(6.0/(fan_in + fan_out))
    wts = tf.get_variable("xavier_weights" + str(name), filter_shape,
        initializer=tf.random_normal_initializer(low, high))
    return wts

def init_bias_shared(shape, name=None):
    biases = tf.get_variable("biases" + str(name), shape,
        initializer=tf.constant_initializer(0.0))
    return biases

def init_weights(shape, name=None):
    return tf.Variable(tf.random_normal(shape, stddev=0.01), name=name)


def init_bias(shape, name=None):
    return tf.Variable(tf.zeros(shape, dtype='float'), name=name)


def batched_matrix_vector_multiply(vector, matrix):
    """ computes x^T A in mini-batches. """
    vector_batch_as_matricies = tf.expand_dims(vector, [1])
    mult_result = tf.batch_matmul(vector_batch_as_matricies, matrix)
    squeezed_result = tf.squeeze(mult_result, [1])
    return squeezed_result


def euclidean_loss_layer(a, b, precision, batch_size):
    """ Math:  out = (action - mlp_out)'*precision*(action-mlp_out)
                    = (u-uhat)'*A*(u-uhat)"""
    scale_factor = tf.constant(2*batch_size, dtype='float')
    uP = batched_matrix_vector_multiply(a-b, precision)
    uPu = tf.reduce_sum(uP*(a-b))  # this last dot product is then summed, so we just the sum all at once.
    return uPu/scale_factor


def get_input_layer(dim_input, dim_output, robot_number):
    """produce the placeholder inputs that are used to run ops forward and backwards.
        net_input: usually an observation.
        action: mu, the ground truth actions we're trying to learn.
        precision: precision matrix used to commpute loss."""
    net_input = tf.placeholder("float", [None, dim_input], name='nn_input' + str(robot_number))
    action = tf.placeholder('float', [None, dim_output], name='action' + str(robot_number))
    precision = tf.placeholder('float', [None, dim_output, dim_output], name='precision' + str(robot_number))
    return net_input, action, precision


def get_mlp_layers(mlp_input, number_layers, dimension_hidden, robot_number):
    """compute MLP with specified number of layers.
        math: sigma(Wx + b)
        for each layer, where sigma is by default relu"""
    cur_top = mlp_input
    for layer_step in range(0, number_layers):
        in_shape = cur_top.get_shape().dims[1].value
        cur_weight = init_weights([in_shape, dimension_hidden[layer_step]], name='w_' + str(layer_step) + 'rn' + str(robot_number))
        cur_bias = init_bias([dimension_hidden[layer_step]], name='b_' + str(layer_step) + 'rn' + str(robot_number))
        if layer_step != number_layers-1:  # final layer has no RELU
            cur_top = tf.nn.relu(tf.matmul(cur_top, cur_weight) + cur_bias)
        else:
            cur_top = tf.matmul(cur_top, cur_weight) + cur_bias

    return cur_top

# def get_mlp_layers_shared(mlp_input, number_layers, dimension_hidden, robot_number):
#     """compute MLP with specified number of layers.
#         math: sigma(Wx + b)
#         for each layer, where sigma is by default relu"""
#     cur_top = mlp_input
#     in_shape = cur_top.get_shape().dims[1].value
#     cur_weight = init_weights([in_shape, dimension_hidden[0]], name='w_' + str(robot_number))
#     cur_bias = init_bias([dimension_hidden[0]], name='b_' + str(robot_number))
#     cur_top = tf.nn.relu(tf.matmul(cur_top, cur_weight) + cur_bias)
#     for layer_step in range(1, number_layers-1):
#         in_shape = cur_top.get_shape().dims[1].value
#         with tf.variable_scope("mlp" + str(layer_step)):
#             cur_weight = init_weights_shared([in_shape, dimension_hidden[layer_step]])
#             cur_bias = init_bias_shared([dimension_hidden[layer_step]])
#             cur_top = tf.nn.relu(tf.matmul(cur_top, cur_weight) + cur_bias)
#     in_shape = cur_top.get_shape().dims[1].value
#     cur_weight = init_weights([in_shape, dimension_hidden[-1]], name='wend_' + str(robot_number))
#     cur_bias = init_bias([dimension_hidden[-1]], name='bend_' + str(robot_number))
#     cur_top = tf.matmul(cur_top, cur_weight) + cur_bias
#     return cur_top



def multi_input_multi_output(dim_input=[27, 27], dim_output=[7, 7], batch_size=25, network_config=None):
    """
    An example of how one might want to specify a network in tensorflow.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
    Returns:
        a TfMap object used to serialize, inputs, outputs, and loss.
    """
    n_layers = 3
    num_robots = len(dim_input)
    nnets = []
    # with tf.variable_scope("shared_ls") as scope:
    for input_size, output_size, robot_number in zip(dim_input, dim_output, range(num_robots)):
        with tf.name_scope("robot" + str(robot_number)):
            dim_hidden = (n_layers - 1) * [42]
            dim_hidden.append(output_size)
            nn_input, action, precision = get_input_layer(input_size, output_size, robot_number)
            mlp_applied = get_mlp_layers(nn_input, n_layers, dim_hidden, robot_number)
            loss_out = get_loss_layer(mlp_out=mlp_applied, action=action, precision=precision, batch_size=batch_size)
            nnets.append(TfMap.init_from_lists([nn_input, action, precision], [mlp_applied], [loss_out]))
        # scope.reuse_variables()
    # import IPython
    # IPython.embed()
    return nnets


def multi_input_multi_output_images(dim_input=[27, 27], dim_output=[7, 7], batch_size=25, network_config=None):
    """
    An example a network in theano that has both state and image inputs.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
        network_config: dictionary of network structure parameters
    Returns:
        a dictionary containing inputs, outputs, and the loss function representing scalar loss.
    """
    # List of indices for state (vector) data and image (tensor) data in observation.
    print 'making multi-input/output-network'
    num_robots = len(dim_input)
    nnets = []
    st_idx = []
    im_idx = []
    i = []
    for robot_number in range(num_robots):
        st_idx.append([])
        im_idx.append([])
        i.append(0)
    #need to fix whatever this is 
    variable_separations = []
    for robot_number, robot_params in enumerate(network_config):
        with tf.name_scope("robot" + str(robot_number)):
            for sensor in robot_params['obs_include']:
                dim = robot_params['sensor_dims'][sensor]
                if sensor in robot_params['obs_image_data']:
                    im_idx[robot_number] = im_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                else:
                    st_idx[robot_number] = st_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                i[robot_number] += dim

            nn_input, action, precision = get_input_layer(dim_input[robot_number], dim_output[robot_number], robot_number)

            state_input = nn_input[:, 0:st_idx[robot_number][-1]+1]
            image_input = nn_input[:, st_idx[robot_number][-1]+1:im_idx[robot_number][-1]+1]

            # image goes through 2 convnet layers
            num_filters = network_config[robot_number]['num_filters']

            im_height = network_config[robot_number]['image_height']
            im_width = network_config[robot_number]['image_width']
            num_channels = network_config[robot_number]['image_channels']
            image_input = tf.reshape(image_input, [-1, im_width, im_height, num_channels])

            #need to resolve this
            dim_hidden = 42
            pool_size = 2
            filter_size = 3
            # we pool twice, each time reducing the image size by a factor of 2.
            conv_out_size = int(im_width/(2.0*pool_size)*im_height/(2.0*pool_size)*num_filters[1])
            #print conv_out_size
            #print len(st_idx)
            print state_input.get_shape().dims[1].value
            first_dense_size = conv_out_size + len(st_idx[robot_number])  #state_input.get_shape().dims[1].value

            # Store layers weight & bias

            weights = {
                'wc1': get_xavier_weights([filter_size, filter_size, num_channels, num_filters[0]], (pool_size, pool_size), name='wc1rn' + str(robot_number)), # 5x5 conv, 1 input, 32 outputs
                'wc2': get_xavier_weights([filter_size, filter_size, num_filters[0], num_filters[1]], (pool_size, pool_size), name='wc2rn' + str(robot_number)), # 5x5 conv, 32 inputs, 64 outputs
                'wd1': init_weights([first_dense_size, dim_hidden], name='wd1rn' + str(robot_number)),
                'out': init_weights([dim_hidden, dim_output[robot_number]], name='outwrn' + str(robot_number))
            }

            biases = {
                'bc1': init_bias([num_filters[0]], name='bc1rn' + str(robot_number)),
                'bc2': init_bias([num_filters[1]], name='bc2rn' + str(robot_number)),
                'bd1': init_bias([dim_hidden], name='bd1rn' + str(robot_number)),
                'out': init_bias([dim_output[robot_number]], name='outbrn' + str(robot_number))
            }

            conv_layer_0 = conv2d(img=image_input, w=weights['wc1'], b=biases['bc1'])

            conv_layer_0 = max_pool(conv_layer_0, k=pool_size)

            conv_layer_1 = conv2d(img=conv_layer_0, w=weights['wc2'], b=biases['bc2'])

            conv_layer_1 = max_pool(conv_layer_1, k=pool_size)

            conv_out_flat = tf.reshape(conv_layer_1, [-1, conv_out_size])

            fc_input = tf.concat(concat_dim=1, values=[conv_out_flat, state_input])

            h_1 = tf.nn.relu(tf.matmul(fc_input, weights['wd1']) + biases['bd1'])
            fc_output = tf.matmul(h_1, weights['out']) + biases['out']

            loss = euclidean_loss_layer(a=action, b=fc_output, precision=precision, batch_size=batch_size)
            variable_separations.append([weights['wc1'], biases['bc1'], weights['wc2'], biases['bc2'], weights['wd1'], biases['bd1'], weights['out'], biases['out']])
            nnets.append(TfMap.init_from_lists([nn_input, action, precision], [fc_output], [loss]))
    return nnets, variable_separations


def multi_input_multi_output_images_shared(dim_input=[27, 27], dim_output=[7, 7], batch_size=25, network_config=None):
    """
    An example a network in theano that has both state and image inputs.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
        network_config: dictionary of network structure parameters
    Returns:
        a dictionary containing inputs, outputs, and the loss function representing scalar loss.
    """
    # List of indices for state (vector) data and image (tensor) data in observation.
    print 'making multi-input/output-network'
    num_robots = len(dim_input)
    nnets = []
    st_idx = []
    im_idx = []
    i = []
    for robot_number in range(num_robots):
        st_idx.append([])
        im_idx.append([])
        i.append(0)
    #need to fix whatever this is 
    variable_separations = []
    with tf.variable_scope("shared_wts"):
        for robot_number, robot_params in enumerate(network_config):
            for sensor in robot_params['obs_include']:
                dim = robot_params['sensor_dims'][sensor]
                if sensor in robot_params['obs_image_data']:
                    im_idx[robot_number] = im_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                else:
                    st_idx[robot_number] = st_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                i[robot_number] += dim

            nn_input, action, precision = get_input_layer(dim_input[robot_number], dim_output[robot_number], robot_number)

            state_input = nn_input[:, 0:st_idx[robot_number][-1]+1]
            image_input = nn_input[:, st_idx[robot_number][-1]+1:im_idx[robot_number][-1]+1]

            # image goes through 2 convnet layers
            num_filters = network_config[robot_number]['num_filters']

            im_height = network_config[robot_number]['image_height']
            im_width = network_config[robot_number]['image_width']
            num_channels = network_config[robot_number]['image_channels']
            image_input = tf.reshape(image_input, [-1, im_width, im_height, num_channels])

            #need to resolve this
            dim_hidden = 42
            pool_size = 2
            filter_size = 3
            # we pool twice, each time reducing the image size by a factor of 2.
            conv_out_size = int(im_width/(2.0*pool_size)*im_height/(2.0*pool_size)*num_filters[1])
            #print conv_out_size
            #print len(st_idx)
            print state_input.get_shape().dims[1].value
            first_dense_size = conv_out_size + len(st_idx[robot_number])  #state_input.get_shape().dims[1].value

            # Store layers weight & bias

            weights = {
                'wc1': get_xavier_weights([filter_size, filter_size, num_channels, num_filters[0]], (pool_size, pool_size), name='wc1rn' + str(robot_number)), # 5x5 conv, 1 input, 32 outputs
                'wd1': init_weights([first_dense_size, dim_hidden], name='wd1rn' + str(robot_number)),
                'out': init_weights([dim_hidden, dim_output[robot_number]], name='outwrn' + str(robot_number))
            }

            biases = {
                'bc1': init_bias([num_filters[0]], name='bc1rn' + str(robot_number)),
                'bd1': init_bias([dim_hidden], name='bd1rn' + str(robot_number)),
                'out': init_bias([dim_output[robot_number]], name='outbrn' + str(robot_number))
            }
            weights['wc2'] = get_xavier_weights_shared([filter_size, filter_size, num_filters[0], num_filters[1]], (pool_size, pool_size), name='wc2rnshared') # 5x5 conv, 32 inputs, 64 outputs
            biases['bc2'] = init_bias_shared([num_filters[1]], name='bc2rnshared')
            tf.get_variable_scope().reuse_variables()
            conv_layer_0 = conv2d(img=image_input, w=weights['wc1'], b=biases['bc1'])

            conv_layer_0 = max_pool(conv_layer_0, k=pool_size)

            conv_layer_1 = conv2d(img=conv_layer_0, w=weights['wc2'], b=biases['bc2'])

            conv_layer_1 = max_pool(conv_layer_1, k=pool_size)

            conv_out_flat = tf.reshape(conv_layer_1, [-1, conv_out_size])

            fc_input = tf.concat(concat_dim=1, values=[conv_out_flat, state_input])

            h_1 = tf.nn.relu(tf.matmul(fc_input, weights['wd1']) + biases['bd1'])
            fc_output = tf.matmul(h_1, weights['out']) + biases['out']

            loss = euclidean_loss_layer(a=action, b=fc_output, precision=precision, batch_size=batch_size)
            variable_separations.append([weights['wc1'], biases['bc1'], weights['wc2'], biases['bc2'], weights['wd1'], biases['bd1'], weights['out'], biases['out']])
            nnets.append(TfMap.init_from_lists([nn_input, action, precision], [fc_output], [loss]))
    return nnets, variable_separations

def multi_input_multi_output_images_shared_multitask(dim_input=[27, 27], dim_output=[7, 7], batch_size=25, network_config=None, same_task_idx=None):
    """
    An example a network in theano that has both state and image inputs.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
        network_config: dictionary of network structure parameters
    Returns:
        a dictionary containing inputs, outputs, and the loss function representing scalar loss.
    """
    # List of indices for state (vector) data and image (tensor) data in observation.
    print 'making multi-input/output-network'
    num_robots = len(dim_input)
    nnets = []
    st_idx = []
    im_idx = []
    i = []
    for robot_number in range(num_robots):
        st_idx.append([])
        im_idx.append([])
        i.append(0)

    robot_task_mapping = {}
    task_num = 0
    for task_robots in same_task_idx:
        for robot_number in task_robots:
            robot_task_mapping[robot_number] = task_num
        task_num += 1
    #need to fix whatever this is 
    variable_separations = []
    with tf.variable_scope("shared_wts"):
        for robot_number, robot_params in enumerate(network_config):
            for sensor in robot_params['obs_include']:
                dim = robot_params['sensor_dims'][sensor]
                if sensor in robot_params['obs_image_data']:
                    im_idx[robot_number] = im_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                else:
                    st_idx[robot_number] = st_idx[robot_number] + list(range(i[robot_number], i[robot_number]+dim))
                i[robot_number] += dim

            nn_input, action, precision = get_input_layer(dim_input[robot_number], dim_output[robot_number], robot_number)

            state_input = nn_input[:, 0:st_idx[robot_number][-1]+1]
            image_input = nn_input[:, st_idx[robot_number][-1]+1:im_idx[robot_number][-1]+1]

            # image goes through 2 convnet layers
            num_filters = network_config[robot_number]['num_filters']

            im_height = network_config[robot_number]['image_height']
            im_width = network_config[robot_number]['image_width']
            num_channels = network_config[robot_number]['image_channels']
            image_input = tf.reshape(image_input, [-1, im_width, im_height, num_channels])

            #need to resolve this
            dim_hidden = 42
            pool_size = 2
            filter_size = 3
            # we pool twice, each time reducing the image size by a factor of 2.
            conv_out_size = int(im_width/(2.0*pool_size)*im_height/(2.0*pool_size)*num_filters[1])
            #print conv_out_size
            #print len(st_idx)
            print state_input.get_shape().dims[1].value
            first_dense_size = conv_out_size + len(st_idx[robot_number])  #state_input.get_shape().dims[1].value

            # Store layers weight & bias

            weights = {
                'wd1': init_weights([first_dense_size, dim_hidden], name='wd1rn' + str(robot_number)),
                'out': init_weights([dim_hidden, dim_output[robot_number]], name='outwrn' + str(robot_number))
            }

            biases = {
                'bd1': init_bias([dim_hidden], name='bd1rn' + str(robot_number)),
                'out': init_bias([dim_output[robot_number]], name='outbrn' + str(robot_number))
            }
            weights['wc1'] = get_xavier_weights_shared([filter_size, filter_size, num_channels, num_filters[0]], (pool_size, pool_size), name='wc1tasknum' + str(robot_task_mapping[robot_number])), # 5x5 conv, 1 input, 32 outputs
            weights['bc1'] = init_bias_shared([num_filters[0]], name='bc1tasknum' + str(robot_task_mapping[robot_number])),
            weights['wc2'] = get_xavier_weights_shared([filter_size, filter_size, num_filters[0], num_filters[1]], (pool_size, pool_size), name='wc2rnshared') # 5x5 conv, 32 inputs, 64 outputs
            biases['bc2'] = init_bias_shared([num_filters[1]], name='bc2rnshared')
            tf.get_variable_scope().reuse_variables()
            conv_layer_0 = conv2d(img=image_input, w=weights['wc1'], b=biases['bc1'])

            conv_layer_0 = max_pool(conv_layer_0, k=pool_size)

            conv_layer_1 = conv2d(img=conv_layer_0, w=weights['wc2'], b=biases['bc2'])

            conv_layer_1 = max_pool(conv_layer_1, k=pool_size)

            conv_out_flat = tf.reshape(conv_layer_1, [-1, conv_out_size])

            fc_input = tf.concat(concat_dim=1, values=[conv_out_flat, state_input])

            h_1 = tf.nn.relu(tf.matmul(fc_input, weights['wd1']) + biases['bd1'])
            fc_output = tf.matmul(h_1, weights['out']) + biases['out']

            loss = euclidean_loss_layer(a=action, b=fc_output, precision=precision, batch_size=batch_size)
            variable_separations.append([weights['wc1'], biases['bc1'], weights['wc2'], biases['bc2'], weights['wd1'], biases['bd1'], weights['out'], biases['out']])
            nnets.append(TfMap.init_from_lists([nn_input, action, precision], [fc_output], [loss]))
    return nnets, variable_separations


def get_loss_layer(mlp_out, action, precision, batch_size):
    """The loss layer used for the MLP network is obtained through this class."""
    return euclidean_loss_layer(a=action, b=mlp_out, precision=precision, batch_size=batch_size)


def example_tf_network(dim_input=27, dim_output=7, batch_size=25, network_config=None):
    """
    An example of how one might want to specify a network in tensorflow.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
    Returns:
        a TfMap object used to serialize, inputs, outputs, and loss.
    """
    n_layers = 2
    dim_hidden = (n_layers - 1) * [40]
    dim_hidden.append(dim_output)

    nn_input, action, precision = get_input_layer(dim_input, dim_output)
    mlp_applied = get_mlp_layers(nn_input, n_layers, dim_hidden)
    loss_out = get_loss_layer(mlp_out=mlp_applied, action=action, precision=precision, batch_size=batch_size)

    return TfMap.init_from_lists([nn_input, action, precision], [mlp_applied], [loss_out])


def multi_modal_network(dim_input=27, dim_output=7, batch_size=25, network_config=None):
    """
    An example a network in theano that has both state and image inputs.

    Args:
        dim_input: Dimensionality of input.
        dim_output: Dimensionality of the output.
        batch_size: Batch size.
        network_config: dictionary of network structure parameters
    Returns:
        a dictionary containing inputs, outputs, and the loss function representing scalar loss.
    """
    # List of indices for state (vector) data and image (tensor) data in observation.
    print 'making multi-modal-network'
    st_idx, im_idx, i = [], [], 0
    for sensor in network_config['obs_include']:
        dim = network_config['sensor_dims'][sensor]
        if sensor in network_config['obs_image_data']:
            im_idx = im_idx + list(range(i, i+dim))
        else:
            st_idx = st_idx + list(range(i, i+dim))
        i += dim

    nn_input, action, precision = get_input_layer(dim_input, dim_output)

    state_input = nn_input[:, 0:st_idx[-1]+1]
    image_input = nn_input[:, st_idx[-1]+1:im_idx[-1]+1]

    # image goes through 2 convnet layers
    num_filters = network_config['num_filters']

    im_height = network_config['image_height']
    im_width = network_config['image_width']
    num_channels = network_config['image_channels']
    image_input = tf.reshape(image_input, [-1, im_width, im_height, num_channels])

    dim_hidden = 10
    pool_size = 2
    filter_size = 3
    # we pool twice, each time reducing the image size by a factor of 2.
    conv_out_size = int(im_width/(2.0*pool_size)*im_height/(2.0*pool_size)*num_filters[1])
    #print conv_out_size
    #print len(st_idx)
    print state_input.get_shape().dims[1].value
    first_dense_size = conv_out_size + len(st_idx)  #state_input.get_shape().dims[1].value

    # Store layers weight & bias
    weights = {
        'wc1': get_xavier_weights([filter_size, filter_size, num_channels, num_filters[0]], (pool_size, pool_size)), # 5x5 conv, 1 input, 32 outputs
        'wc2': get_xavier_weights([filter_size, filter_size, num_filters[0], num_filters[1]], (pool_size, pool_size)), # 5x5 conv, 32 inputs, 64 outputs
        'wd1': init_weights([first_dense_size, dim_hidden]),
        'out': init_weights([dim_hidden, dim_output])
    }

    biases = {
        'bc1': init_bias([num_filters[0]]),
        'bc2': init_bias([num_filters[1]]),
        'bd1': init_bias([dim_hidden]),
        'out': init_bias([dim_output])
    }

    conv_layer_0 = conv2d(img=image_input, w=weights['wc1'], b=biases['bc1'])

    conv_layer_0 = max_pool(conv_layer_0, k=pool_size)

    conv_layer_1 = conv2d(img=conv_layer_0, w=weights['wc2'], b=biases['bc2'])

    conv_layer_1 = max_pool(conv_layer_1, k=pool_size)

    conv_out_flat = tf.reshape(conv_layer_1, [-1, conv_out_size])

    fc_input = tf.concat(concat_dim=1, values=[conv_out_flat, state_input])

    h_1 = tf.nn.relu(tf.matmul(fc_input, weights['wd1']) + biases['bd1'])
    fc_output = tf.matmul(h_1, weights['out']) + biases['out']

    loss = euclidean_loss_layer(a=action, b=fc_output, precision=precision, batch_size=batch_size)
    return TfMap.init_from_lists([nn_input, action, precision], [fc_output], [loss])


def conv2d(img, w, b):
    #print img.get_shape().dims[3].value
    return tf.nn.relu(tf.nn.bias_add(tf.nn.conv2d(img, w, strides=[1, 1, 1, 1], padding='SAME'), b))


def max_pool(img, k):
    return tf.nn.max_pool(img, ksize=[1, k, k, 1], strides=[1, k, k, 1], padding='SAME')


def get_xavier_weights(filter_shape, poolsize=(2, 2), name=None):
    fan_in = np.prod(filter_shape[1:])
    fan_out = (filter_shape[0] * np.prod(filter_shape[2:]) //
               np.prod(poolsize))

    low = -4*np.sqrt(6.0/(fan_in + fan_out)) # use 4 for sigmoid, 1 for tanh activation
    high = 4*np.sqrt(6.0/(fan_in + fan_out))
    return tf.Variable(tf.random_uniform(filter_shape, minval=low, maxval=high, dtype=tf.float32), name=name)