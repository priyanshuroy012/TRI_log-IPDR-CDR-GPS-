from keras.models import Model
from keras.layers import Input, Dense
from keras import regularizers
import numpy as np

def train_autoencoder_model(X_scaled, encoding_dim=8, epochs=50):
    input_dim = X_scaled.shape[1]
    input_layer = Input(shape=(input_dim,))
    encoded = Dense(encoding_dim, activation="relu", activity_regularizer=regularizers.l1(1e-4))(input_layer)
    decoded = Dense(input_dim, activation="linear")(encoded)
    autoencoder = Model(inputs=input_layer, outputs=decoded)
    autoencoder.compile(optimizer="adam", loss="mse")
    autoencoder.fit(X_scaled, X_scaled, epochs=epochs, batch_size=32, shuffle=True, validation_split=0.1, verbose=0)
    return autoencoder

def compute_autoencoder_anomalies(autoencoder, X_scaled, threshold_quantile=0.95):
    X_pred = autoencoder.predict(X_scaled)
    mse = np.mean(np.square(X_scaled - X_pred), axis=1)
    threshold = np.quantile(mse, threshold_quantile)
    return (mse > threshold).astype(int)
