import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image  # type: ignore
from tensorflow.keras.applications.efficientnet import preprocess_input  # type: ignore

import cv2
import matplotlib.pyplot as plt

def gradcam(model, img_path, save_path, class_index=None, size=(224,224)):
    if model is None:
        return
    img = image.load_img(img_path, target_size=size)
    x = image.img_to_array(img)[None]
    x = preprocess_input(x)
    preds = model.predict(x, verbose=0)
    if class_index is None:
        class_index = int(np.argmax(preds[0]))
    # find last conv-like layer
    layer_name = None
    for layer in reversed(model.layers):
        try:
            shape = layer.output.shape
            if len(shape) == 4:
                layer_name = layer.name
                break
        except Exception:
            continue
    if layer_name is None:
        return
    grad_model = tf.keras.models.Model([model.inputs], [model.get_layer(layer_name).output, model.output])
    with tf.GradientTape() as tape:
        conv_out, predictions = grad_model(x)
        loss = predictions[:, class_index]
    grads = tape.gradient(loss, conv_out)[0]
    weights = tf.reduce_mean(grads, axis=(0,1))
    cam = tf.reduce_sum(tf.multiply(weights, conv_out[0]), axis=-1).numpy()
    cam = np.maximum(cam, 0)
    if cam.max() != 0:
        cam = cam / (cam.max() + 1e-10)
    cam = cv2.resize(cam, size)
    img_raw = cv2.imread(img_path)
    img_raw = cv2.resize(img_raw, size)
    heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img_raw, 0.5, heatmap, 0.5, 0)
    plt.imsave(save_path, cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
