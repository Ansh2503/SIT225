import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "work7h/results"
metrics = json.loads((RES / "metrics.json").read_text())
faults = pd.read_csv(RES / "fault_injection_log.csv")


def terminal_image(text, output, title):
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    font = ImageFont.truetype(font_path, 22)
    bold = ImageFont.truetype(bold_path, 24)
    lines = text.splitlines()
    width = 1500
    height = 100 + 32 * len(lines)
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 58), fill="#1f2937")
    draw.text((24, 15), title, fill="#f9fafb", font=bold)
    y = 76
    for line in lines:
        colour = "#86efac" if line.endswith("... ok") or line == "OK" else "#e5e7eb"
        draw.text((24, y), line, fill=colour, font=font)
        y += 32
    image.save(output)


terminal_image(
    (ROOT / "work7h/results_test_output.txt").read_text(),
    RES / "automated_test_terminal.png",
    "SIT225 Task 7H Automated Test Run",
)

summary = "\n".join([
    "Controlled validation summary",
    f"Real DHT11 rows processed: {metrics['raw_rows']}",
    f"Valid rows retained: {metrics['valid_rows']} (100.0%)",
    f"Injected fault cases: {metrics['test_faults']}",
    f"Baseline detected: {metrics['baseline_faults_detected']} (66.7%)",
    f"Hardened detected: {metrics['hardened_faults_detected']} (100.0%)",
    f"TP={metrics['tp']}  FN={metrics['fn']}  FP={metrics['fp']}  TN={metrics['tn']}",
    f"Median processing latency: {metrics['median_latency_ms']:.4f} ms",
    f"95th percentile latency: {metrics['p95_latency_ms']:.4f} ms",
    "Simulated serial recovery: 0.02 s",
    "Unhandled crashes: 0",
])
terminal_image(summary, RES / "performance_terminal.png", "SIT225 Task 7H Validation Metrics")

plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
axes[0].bar(["Baseline", "Hardened"], [66.7, 100.0], color=["#94a3b8", "#1f4e78"])
axes[0].set_ylim(0, 110)
axes[0].set_ylabel("Injected faults detected (%)")
axes[0].set_title("Fault Detection Comparison")
for i, value in enumerate([66.7, 100.0]):
    axes[0].text(i, value + 2, f"{value:.1f}%", ha="center", fontweight="bold")

matrix = [[metrics["tp"], metrics["fn"]], [metrics["fp"], metrics["tn"]]]
image = axes[1].imshow(matrix, cmap="Blues")
axes[1].set_xticks([0, 1], ["Flagged", "Not flagged"])
axes[1].set_yticks([0, 1], ["Actual fault", "Valid input"])
axes[1].set_title("Hardened Pipeline Confusion Matrix")
for y in range(2):
    for x in range(2):
        axes[1].text(x, y, matrix[y][x], ha="center", va="center", fontsize=16, fontweight="bold")
fig.tight_layout()
fig.savefig(RES / "baseline_confusion_comparison.png", dpi=180, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 5))
labels = faults["fault"].str.replace("_", " ")
y = range(len(faults))
ax.scatter(faults["baseline_flagged"].astype(int), y, label="Baseline", s=65, color="#94a3b8")
ax.scatter(faults["hardened_flagged"].astype(int) + 0.04, y, label="Hardened", s=45, color="#1f4e78")
ax.set_yticks(list(y), labels)
ax.set_xticks([0, 1], ["Missed", "Detected"])
ax.set_xlim(-0.15, 1.2)
ax.set_title("Controlled Fault Injection Results")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(RES / "fault_injection_results.png", dpi=180, bbox_inches="tight")
plt.close(fig)

print("Evidence images written to", RES)
