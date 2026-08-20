from pathlib import Path
import numpy as np

from simple_mlp import MLP, load_images, load_labels

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/MNIST/raw"
MODEL = ROOT / "assets/mlp_model.npz"
OUTPUT = ROOT / "assets/mlp_inference_snapshot.npz"


def main(sample_index: int = 0) -> None:
    X = load_images(RAW / "t10k-images-idx3-ubyte")
    y = load_labels(RAW / "t10k-labels-idx1-ubyte")

    mlp = MLP(784, 8, 10, learning_rate=0.1)
    mlp.load_model(MODEL)
    x = X[sample_index:sample_index + 1]
    output = mlp.forward(x)
    prediction = int(np.argmax(output[0]))

    np.savez(
        OUTPUT,
        sample_index=np.array(sample_index),
        image=x[0].reshape(28, 28),
        x=x[0],
        W1=mlp.W1,
        b1=mlp.b1[0],
        Z1=mlp.Z1[0],
        Y1=mlp.Y1[0],
        W2=mlp.W2,
        b2=mlp.b2[0],
        Z2=mlp.Z2[0],
        Y2=mlp.Y2[0],
        label=np.array(int(y[sample_index])),
        prediction=np.array(prediction),
        input_contribution=x[0, :, None] * mlp.W1,
        hidden_contribution=mlp.Y1[0, :, None] * mlp.W2,
    )
    print(f"snapshot={OUTPUT}")
    print(f"sample={sample_index} label={int(y[sample_index])} prediction={prediction}")
    print("hidden=", np.array2string(mlp.Y1[0], precision=4))
    print("output=", np.array2string(mlp.Y2[0], precision=4))


if __name__ == "__main__":
    main()
