#!/usr/bin/env python
"""
Depth Anything V2 Domain Adaptation & Fine-Tuning Script on GAMUS Benchmark Dataset.

Usage:
  python scripts/train.py --data-dir demo_data/gamus --epochs 3 --lr 1e-4
"""

import os
import sys
import argparse
import logging
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from depthwizard.datasets.gamus import GAMUSDataset, create_sample_gamus_dataset
from depthwizard.models.depth_anything import DepthAnythingPredictor

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("depthwizard.train")


class DomainAdaptedDepthModel(nn.Module):
    """
    Lightweight Domain Adaptation Head on top of Depth Anything V2 features.
    Freezes ViT encoder backbone and fine-tunes regression projection.
    """

    def __init__(self, model_size: str = "base"):
        super().__init__()
        self.predictor = DepthAnythingPredictor(model_size=model_size)

        # Adapter linear regression projection layers (a * depth + b per pixel feature)
        self.adapter = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 1, kernel_size=1),
        )

    def forward(self, rgb_tensor: torch.Tensor) -> torch.Tensor:
        # Predict relative depth per image batch
        B = rgb_tensor.shape[0]
        preds = []
        for i in range(B):
            img_np = (rgb_tensor[i].permute(1, 2, 0).cpu().numpy() * 255.0).astype("uint8")
            rel = self.predictor.predict(img_np)
            preds.append(torch.from_numpy(rel).unsqueeze(0).unsqueeze(0))

        rel_t = torch.cat(preds, dim=0).to(rgb_tensor.device)
        adapted = rel_t + self.adapter(rel_t)
        return adapted


def train_model(data_dir: str, epochs: int = 3, lr: float = 1e-4, batch_size: int = 2):
    """Executes fine-tuning / domain adaptation training loop."""
    logger.info(f"=== Depth Anything V2 Domain Adaptation on GAMUS Dataset ({data_dir}) ===")
    os.makedirs("checkpoints", exist_ok=True)

    # Load Train & Validation datasets
    train_dataset = GAMUSDataset(data_dir=data_dir, split="train")
    val_dataset = GAMUSDataset(data_dir=data_dir, split="val")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = DomainAdaptedDepthModel(model_size="base").to(device)

    optimizer = torch.optim.AdamW(model.adapter.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.L1Loss()

    logger.info(f"Training on device: {device} for {epochs} epochs...")

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            target_dsm = batch["dsm"].to(device)

            optimizer.zero_grad()
            outputs = model(images)

            # Mask valid target values
            valid_mask = ~torch.isnan(target_dsm) & (target_dsm > -9000.0)
            if valid_mask.any():
                loss = criterion(outputs[valid_mask], target_dsm[valid_mask])
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

        train_loss /= max(1, len(train_loader))

        # Validation Step
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                target_dsm = batch["dsm"].to(device)
                outputs = model(images)
                valid_mask = ~torch.isnan(target_dsm) & (target_dsm > -9000.0)
                if valid_mask.any():
                    loss = criterion(outputs[valid_mask], target_dsm[valid_mask])
                    val_loss += loss.item()

        val_loss /= max(1, len(val_loader))
        logger.info(f"Epoch [{epoch}/{epochs}] - Train L1 Loss: {train_loss:.4f} | Val L1 Loss: {val_loss:.4f}")

    checkpoint_path = os.path.join("checkpoints", "depth_anything_v2_gamus.pth")
    torch.save(model.state_dict(), checkpoint_path)
    logger.info(f"Saved domain-adapted model checkpoint to {checkpoint_path}")


def main():
    parser = argparse.ArgumentParser(description="Depth Anything V2 Domain Adaptation Training")
    parser.add_argument("--data-dir", default="demo_data/gamus", help="Path to GAMUS dataset directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    args = parser.parse_args()

    train_model(data_dir=args.data_dir, epochs=args.epochs, lr=args.lr)


if __name__ == "__main__":
    main()
