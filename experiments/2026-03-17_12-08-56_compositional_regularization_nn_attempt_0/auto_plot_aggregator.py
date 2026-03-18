#!/usr/bin/env python3
"""
Final aggregated figures for Enhancing Compositional Generalization in Neural Networks via Compositional Regularization.
This script loads experimental .npy data from baseline (dropout tuning) and research (layer tuning) experiments,
then generates consolidated, publication-ready figures. All figures are stored in the figures directory.
Each figure is generated in its own try/except block so that a failure in one does not prevent the rest from running.
All labels and titles are free of underscores.
"""

import os
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.size": 16,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
})

def clean_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

os.makedirs("figures", exist_ok=True)

baseline_file = "experiment_results/experiment_1b296c0cab174e9a9ea3385b5651dc9e_proc_349114/experiment_data.npy"
research_file = "experiment_results/experiment_716f18cc6e0d4e6ca4740b903b12d5a2_proc_404878/experiment_data.npy"

try:
    baseline_data = np.load(baseline_file, allow_pickle=True).item()
except Exception as e:
    print(f"Error loading baseline data from {baseline_file}: {e}")
    baseline_data = {}

try:
    research_data = np.load(research_file, allow_pickle=True).item()
except Exception as e:
    print(f"Error loading research data from {research_file}: {e}")
    research_data = {}

try:
    base_exp = baseline_data["dropout_tuning"]["arithmetic"]
    # Use the keys as they are stored (likely strings like '0.1', '0.2', etc.)
    dropout_rate_keys = list(base_exp["systematicity"].keys())
    dropout_rates = sorted(dropout_rate_keys, key=lambda k: float(k))
except Exception as e:
    print(f"Error extracting baseline dropout rates: {e}")
    dropout_rates = []

try:
    res_exp = research_data["layer_tuning"]
    layer_configs = [1, 2, 3, 4]
except Exception as e:
    print(f"Error extracting research layer tuning data: {e}")
    layer_configs = []

# Figure 1: Aggregated Baseline Results (Three Subplots)
try:
    fig, axs = plt.subplots(1, 3, figsize=(20, 6))

    for i, dr in enumerate(dropout_rates):
        try:
            train_losses = base_exp["metrics"]["train"][i]
            test_losses = base_exp["metrics"]["test"][i]
            epochs = range(1, len(train_losses)+1)
            axs[0].plot(epochs, train_losses, label=f"Train (Dropout {dr})", linestyle="-")
            axs[0].plot(epochs, test_losses, label=f"Test (Dropout {dr})", linestyle="--")
        except Exception as e:
            print(f"Error in baseline loss curves for dropout {dr}: {e}")
    axs[0].set_xlabel("Epoch")
    axs[0].set_ylabel("Loss")
    axs[0].set_title("Loss Curves for Different Dropout Rates")
    axs[0].legend()
    clean_axes(axs[0])
    
    for dr in dropout_rates:
        try:
            syst = base_exp["systematicity"][dr]
            epochs = range(1, len(syst)+1)
            axs[1].plot(epochs, syst, label=f"Dropout {dr}")
        except Exception as e:
            print(f"Error in baseline systematicity for dropout {dr}: {e}")
    axs[1].set_xlabel("Epoch")
    axs[1].set_ylabel("Systematicity Score")
    axs[1].set_title("Systematicity Score Across Epochs")
    axs[1].legend()
    clean_axes(axs[1])
    
    final_test_losses = []
    for i, dr in enumerate(dropout_rates):
        try:
            test_series = base_exp["metrics"]["test"][i]
            final_test_losses.append(test_series[-1])
        except Exception as e:
            print(f"Error extracting final test loss for dropout {dr}: {e}")
            final_test_losses.append(0)
    axs[2].bar([dr for dr in dropout_rates], final_test_losses, color="skyblue")
    axs[2].set_xlabel("Dropout Rate")
    axs[2].set_ylabel("Final Test Loss")
    axs[2].set_title("Final Test Loss vs Dropout Rate")
    clean_axes(axs[2])
    
    plt.tight_layout()
    fig.savefig(os.path.join("figures", "aggregated_baseline.png"), dpi=300)
    plt.close(fig)
except Exception as e:
    print(f"Error generating aggregated baseline figure: {e}")

# Figure 2: Aggregated Research Results (Three Subplots)
try:
    fig, axs = plt.subplots(1, 3, figsize=(20, 6))
    colors = ["b", "g", "r", "c"]
    
    for i, layers in enumerate(layer_configs):
        try:
            t_losses = res_exp["metrics"][f"layers_{layers}"]["train"]
            epochs = range(1, len(t_losses)+1)
            axs[0].plot(epochs, t_losses, color=colors[i], label=f"{layers} Layer(s)")
        except Exception as e:
            print(f"Error in research training loss for {layers} layer(s): {e}")
    axs[0].set_xlabel("Epoch")
    axs[0].set_ylabel("Training Loss")
    axs[0].set_title("Training Loss for Different Layer Configurations")
    axs[0].legend()
    clean_axes(axs[0])
    
    for i, layers in enumerate(layer_configs):
        try:
            te_losses = res_exp["metrics"][f"layers_{layers}"]["test"]
            epochs = range(1, len(te_losses)+1)
            axs[1].plot(epochs, te_losses, color=colors[i], label=f"{layers} Layer(s)")
        except Exception as e:
            print(f"Error in research test loss for {layers} layer(s): {e}")
    axs[1].set_xlabel("Epoch")
    axs[1].set_ylabel("Test Loss")
    axs[1].set_title("Test Loss for Different Layer Configurations")
    axs[1].legend()
    clean_axes(axs[1])
    
    for i, layers in enumerate(layer_configs):
        try:
            syst = res_exp["systematicity"][f"layers_{layers}"]
            epochs = range(1, len(syst)+1)
            axs[2].plot(epochs, syst, color=colors[i], label=f"{layers} Layer(s)")
        except Exception as e:
            print(f"Error in research systematicity for {layers} layer(s): {e}")
    axs[2].set_xlabel("Epoch")
    axs[2].set_ylabel("Systematicity Score")
    axs[2].set_title("Systematicity Across Epochs")
    axs[2].legend()
    clean_axes(axs[2])
    
    plt.tight_layout()
    fig.savefig(os.path.join("figures", "aggregated_research.png"), dpi=300)
    plt.close(fig)
except Exception as e:
    print(f"Error generating aggregated research figure: {e}")

# Figure 3: Baseline Best Dropout Detailed Results
try:
    best_dropout = "0.3"
    if best_dropout in dropout_rates:
        idx = dropout_rates.index(best_dropout)
    else:
        idx = None
    if idx is not None:
        train_losses = base_exp["metrics"]["train"][idx]
        test_losses = base_exp["metrics"]["test"][idx]
        epochs = range(1, len(train_losses)+1)
        
        fig, axs = plt.subplots(2, 1, figsize=(10, 10))
        axs[0].plot(epochs, train_losses, color="mediumblue", marker="o", label="Training Loss")
        axs[0].set_xlabel("Epoch")
        axs[0].set_ylabel("Loss")
        axs[0].set_title("Baseline Dropout 0.3 Training Loss")
        axs[0].legend()
        clean_axes(axs[0])
        
        axs[1].plot(epochs, test_losses, color="firebrick", marker="o", label="Test Loss")
        axs[1].set_xlabel("Epoch")
        axs[1].set_ylabel("Loss")
        axs[1].set_title("Baseline Dropout 0.3 Test Loss")
        axs[1].legend()
        clean_axes(axs[1])
        
        plt.tight_layout()
        fig.savefig(os.path.join("figures", "baseline_best_dropout.png"), dpi=300)
        plt.close(fig)
    else:
        print("Best dropout rate 0.3 not found in baseline data.")
except Exception as e:
    print(f"Error generating baseline best dropout figure: {e}")

# Figure 4: Research Best Layer Detailed Results
try:
    best_layer = 1
    train_losses = res_exp["metrics"][f"layers_{best_layer}"]["train"]
    test_losses = res_exp["metrics"][f"layers_{best_layer}"]["test"]
    epochs = range(1, len(train_losses)+1)
    
    fig, axs = plt.subplots(2, 1, figsize=(10, 10))
    axs[0].plot(epochs, train_losses, color="darkgreen", marker="o", label="Training Loss")
    axs[0].set_xlabel("Epoch")
    axs[0].set_ylabel("Loss")
    axs[0].set_title("Research 1 Layer Training Loss")
    axs[0].legend()
    clean_axes(axs[0])
    
    axs[1].plot(epochs, test_losses, color="darkorange", marker="o", label="Test Loss")
    axs[1].set_xlabel("Epoch")
    axs[1].set_ylabel("Loss")
    axs[1].set_title("Research 1 Layer Test Loss")
    axs[1].legend()
    clean_axes(axs[1])
    
    plt.tight_layout()
    fig.savefig(os.path.join("figures", "research_best_layer.png"), dpi=300)
    plt.close(fig)
except Exception as e:
    print(f"Error generating research best layer figure: {e}")

# Figure 5: Final Systematicity Comparison between Baseline and Research
try:
    final_syst_baseline = []
    for dr in dropout_rates:
        try:
            syst_series = base_exp["systematicity"][dr]
            final_syst_baseline.append(syst_series[-1])
        except Exception as e:
            print(f"Error extracting baseline systematicity for dropout {dr}: {e}")
            final_syst_baseline.append(0)
            
    final_syst_research = []
    for layers in layer_configs:
        try:
            syst_series = res_exp["systematicity"][f"layers_{layers}"]
            final_syst_research.append(syst_series[-1])
        except Exception as e:
            print(f"Error extracting research systematicity for {layers} layer(s): {e}")
            final_syst_research.append(0)
            
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    axs[0].bar([dr for dr in dropout_rates], final_syst_baseline, color="mediumpurple")
    axs[0].set_xlabel("Dropout Rate")
    axs[0].set_ylabel("Final Systematicity Score")
    axs[0].set_title("Baseline Final Systematicity")
    clean_axes(axs[0])
    
    axs[1].bar([str(l) for l in layer_configs], final_syst_research, color="seagreen")
    axs[1].set_xlabel("Number of Layers")
    axs[1].set_ylabel("Final Systematicity Score")
    axs[1].set_title("Research Final Systematicity")
    clean_axes(axs[1])
    
    plt.tight_layout()
    fig.savefig(os.path.join("figures", "final_systematicity_comparison.png"), dpi=300)
    plt.close(fig)
except Exception as e:
    print(f"Error generating final systematicity comparison figure: {e}")

print("All final figures generated and saved in the 'figures' directory.")