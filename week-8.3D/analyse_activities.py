import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DATA_FOLDER = Path("captured_activity_data")
OUTPUT_FOLDER = Path("analysis_output")
OUTPUT_FOLDER.mkdir(exist_ok=True)

LABEL_NAMES = {
    0: "No activity",
    1: "Waving",
    2: "Shaking"
}

annotations = pd.read_csv(
    DATA_FOLDER / "annotations.csv"
)

annotations["activity_label"] = (
    annotations["activity_label"].astype(int)
)

feature_rows = []
activity_series = {0: [], 1: [], 2: []}


for _, annotation in annotations.iterrows():
    filename = annotation["filename"]
    label = annotation["activity_label"]

    data = pd.read_csv(DATA_FOLDER / filename)

    if data.empty:
        continue

    x = data["x"].astype(float)
    y = data["y"].astype(float)
    z = data["z"].astype(float)

    magnitude = np.sqrt(x**2 + y**2 + z**2)

    feature_rows.append({
        "filename": filename,
        "activity_label": label,
        "activity": LABEL_NAMES[label],
        "mean_magnitude": magnitude.mean(),
        "standard_deviation": magnitude.std(),
        "maximum_magnitude": magnitude.max(),
        "x_range": x.max() - x.min(),
        "y_range": y.max() - y.min(),
        "z_range": z.max() - z.min()
    })

    activity_series[label].append({
        "filename": filename,
        "magnitude": magnitude.to_numpy()
    })


features = pd.DataFrame(feature_rows)

features.to_csv(
    OUTPUT_FOLDER / "activity_features.csv",
    index=False
)

summary = (
    features.groupby("activity")
    .agg({
        "filename": "count",
        "mean_magnitude": "mean",
        "standard_deviation": "mean",
        "maximum_magnitude": "mean",
        "x_range": "mean",
        "y_range": "mean",
        "z_range": "mean"
    })
    .rename(columns={"filename": "sample_count"})
)

summary.to_csv(
    OUTPUT_FOLDER / "activity_summary.csv"
)

print("\nActivity summary:")
print(summary)


# Graph 1: feature comparison
figure, axes = plt.subplots(
    1,
    3,
    figsize=(16, 5)
)

features.boxplot(
    column="standard_deviation",
    by="activity",
    ax=axes[0],
    grid=False
)

axes[0].set_title("Movement Variation")
axes[0].set_xlabel("Activity")
axes[0].set_ylabel("Standard Deviation")

features.boxplot(
    column="maximum_magnitude",
    by="activity",
    ax=axes[1],
    grid=False
)

axes[1].set_title("Maximum Acceleration")
axes[1].set_xlabel("Activity")
axes[1].set_ylabel("Maximum Magnitude")

range_means = (
    features.groupby("activity")[
        ["x_range", "y_range", "z_range"]
    ]
    .mean()
)

range_means.plot(
    kind="bar",
    ax=axes[2],
    color=["red", "green", "blue"]
)

axes[2].set_title("Average Axis Range")
axes[2].set_xlabel("Activity")
axes[2].set_ylabel("Acceleration Range")
axes[2].tick_params(axis="x", rotation=15)
axes[2].legend(["X", "Y", "Z"])

figure.suptitle(
    "Accelerometer Feature Comparison by Activity",
    fontsize=16
)

plt.tight_layout()

plt.savefig(
    OUTPUT_FOLDER / "activity_comparison.png",
    dpi=200,
    bbox_inches="tight"
)

plt.close()


# Graph 2: multiple patterns from each activity
figure, axes = plt.subplots(
    3,
    1,
    figsize=(14, 12)
)

colours = {
    0: "gray",
    1: "blue",
    2: "red"
}

for label in [0, 1, 2]:
    selected = activity_series[label][:3]

    for instance_number, instance in enumerate(
        selected,
        start=1
    ):
        magnitude = instance["magnitude"]

        axes[label].plot(
            range(len(magnitude)),
            magnitude,
            label=f"Instance {instance_number}",
            alpha=0.8
        )

    axes[label].set_title(
        f"{LABEL_NAMES[label]}: Three Instances"
    )

    axes[label].set_xlabel("Reading Number")
    axes[label].set_ylabel("Acceleration Magnitude")
    axes[label].legend()
    axes[label].grid(alpha=0.3)

plt.tight_layout()

plt.savefig(
    OUTPUT_FOLDER / "multiple_activity_patterns.png",
    dpi=200,
    bbox_inches="tight"
)

plt.close()


# Copy three representative images for each activity
for label in [0, 1, 2]:
    selected_rows = annotations[
        annotations["activity_label"] == label
    ].head(3)

    for number, (_, row) in enumerate(
        selected_rows.iterrows(),
        start=1
    ):
        image_name = Path(row["filename"]).with_suffix(
            ".jpg"
        )

        source = DATA_FOLDER / image_name

        destination = OUTPUT_FOLDER / (
            f"label_{label}_{LABEL_NAMES[label].replace(' ', '_')}"
            f"_instance_{number}.jpg"
        )

        if source.exists():
            shutil.copy2(source, destination)


print("\nAnalysis complete.")
print("Results saved in analysis_output.")
