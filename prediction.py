import joblib
import numpy as np
import pandas as pd


def predict_earthquake_wave(pga: float, naturalfreq: int) -> tuple[str, str]:
    model_path = "./earthquake_model.joblib"
    model = joblib.load(model_path)

    classification = {
        0: "<div class='text-green-500'>Minor Earthquake. Stay in place!</div>",
        1: "<div class='text-green-500'>Moderate/Severe Earthquake. Evacuate immediately!</div>",
    }

    # features = np.array([pga, naturalfreq]).reshape(1, -1)
    # features_df = pd.DataFrame(features, columns=["PGA", "NaturalFreq"])

    features_df = pd.DataFrame(
        np.array([[pga, naturalfreq]]), columns=["PGA", "NaturalFreq"]
    )
    predicted_number = model.predict(features_df).item()
    # print(f"Predicted number: {predicted_number}")
    # predicted_proba = model.predict_proba(features_df)
    # print(f"Predicted probability: {predicted_proba}")

    # Print the predicted class
    return (
        f"<strong>{classification[predicted_number]}</strong>",
        f"<strong>{0}%</strong><br>",
    )
