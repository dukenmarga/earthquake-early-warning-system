import joblib
import numpy as np
import pandas as pd


# Open the ML/AI model and make inference
def predict_earthquake_wave(pga: float, naturalfreq: int) -> tuple[str, str]:
    model_path = "./earthquake_model.joblib"
    model = joblib.load(model_path)

    classification = {
        0: "<div style='color:green'><strong>Minor Earthquake. Stay in place!</strong></div>",
        1: "<div style='color:red'><strong>Moderate/Severe Earthquake. Evacuate immediately!</strong></div>",
    }

    features_df = pd.DataFrame(
        np.array([[pga, naturalfreq]]), columns=["PGA", "NaturalFreq"]
    )
    predicted_number = model.predict(features_df).item()

    return (
        f"{classification[predicted_number]}",
        f"{0}%",
    )
