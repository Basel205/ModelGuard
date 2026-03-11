"""
mnist_model.py — MNIST Classifier Architecture

Simple but effective CNN for MNIST digit classification.
Kept intentionally simple so:
- Training is fast (< 1 minute)
- Model file is small (easy to demo tampering)
- Architecture is universally understood

Architecture:
    Input (1x28x28)
        → Conv2d(1, 32, 3) + ReLU + MaxPool
        → Conv2d(32, 64, 3) + ReLU + MaxPool
        → Flatten
        → Linear(1600, 128) + ReLU + Dropout
        → Linear(128, 10)
        → LogSoftmax
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class MNISTClassifier(nn.Module):
    """
    CNN classifier for MNIST handwritten digits.
    Input:  (batch, 1, 28, 28) float tensor
    Output: (batch, 10) log-probabilities
    """

    def __init__(self):
        super(MNISTClassifier, self).__init__()

        # Convolutional layers
        self.conv1 = nn.Conv2d(
            in_channels  = 1,
            out_channels = 32,
            kernel_size  = 3,
            padding      = 1,
        )
        self.conv2 = nn.Conv2d(
            in_channels  = 32,
            out_channels = 64,
            kernel_size  = 3,
            padding      = 1,
        )

        # Pooling
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        # Fully connected layers
        # After 2x pooling on 28x28: 28 → 14 → 7
        # 64 channels * 7 * 7 = 3136
        self.fc1     = nn.Linear(64 * 7 * 7, 128)
        self.fc2     = nn.Linear(128, 10)
        self.dropout = nn.Dropout(p=0.25)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Block 1: Conv → ReLU → Pool
        x = self.pool(F.relu(self.conv1(x)))

        # Block 2: Conv → ReLU → Pool
        x = self.pool(F.relu(self.conv2(x)))

        # Flatten
        x = x.view(x.size(0), -1)

        # Fully connected
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)

        return F.log_softmax(x, dim=1)

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Return predicted class indices."""
        with torch.no_grad():
            logits = self.forward(x)
            return torch.argmax(logits, dim=1)

    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_architecture_summary(self) -> dict:
        """Return architecture info for provenance metadata."""
        return {
            "architecture":  "CNN",
            "input_shape":   "1x28x28",
            "output_classes": 10,
            "parameters":    self.count_parameters(),
            "layers": {
                "conv1":   "Conv2d(1→32, k=3, p=1)",
                "conv2":   "Conv2d(32→64, k=3, p=1)",
                "pool":    "MaxPool2d(2x2)",
                "fc1":     "Linear(3136→128)",
                "dropout": "Dropout(0.25)",
                "fc2":     "Linear(128→10)",
                "output":  "LogSoftmax",
            }
        }