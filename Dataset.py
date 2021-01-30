from __future__ import print_function, division
import os
import torch
from skimage import io
import numpy as np
from torch.utils.data import Dataset
from torchvision import transforms
import glob
import random
from typing import List


class RemoveMinimap(object):
    """Remove minimap (black square) from the sequence"""

    def __init__(self, hide_map_prob):
        """
        Init

        Input:
        -hide_map_prob: Probability for removing the minimap (black square)
          from the sequence of images (0<=hide_map_prob<=1)
        """
        self.hide_map_prob = hide_map_prob

    def __call__(self, sample):
        image, y = (
            sample["image"],
            sample["y"],
        )

        width: int = int(image.shape[1] / 5)

        if random.random() <= self.hide_map_prob:
            for j in range(0, 5):
                image[215:, j * width : (j * width) + 80] = np.zeros(
                    (55, 80, 3), dtype=image.dtype
                )

        return {
            "image": image,
            "y": y,
        }


class RemoveImage(object):
    """Remove images (black square) from the sequence"""

    def __init__(self, dropout_images_prob):
        """
        Init

        Input:
        - dropout_images_prob List of 5 floats or None, probability for removing each input image during training
         (black image) from a training example (0<=dropout_images_prob<=1)
        """
        self.dropout_images_prob = dropout_images_prob

    def __call__(self, sample):
        image, y = (
            sample["image"],
            sample["y"],
        )
        width: int = int(image.shape[1] / 5)

        for j in range(0, 5):
            if random.random() <= self.dropout_images_prob[j]:
                image[:, j * width : (j + 1) * width] = np.zeros(
                    (image.shape[0], width, image.shape[2]), dtype=image.dtype
                )

        return {
            "image": image,
            "y": y,
        }


class SplitImages(object):
    """Splits the sequence into 5 images"""

    def __call__(self, sample):
        image, y = sample["image"], sample["y"]
        width: int = int(image.shape[1] / 5)
        return {
            "image1": image[:, 0:width],
            "image2": image[:, width : width * 2],
            "image3": image[:, width * 2 : width * 3],
            "image4": image[:, width * 3 : width * 4],
            "image5": image[:, width * 4 : width * 5],
            "y": y,
        }


class ToTensor(object):
    """Convert ndarrays in sample to Tensors."""

    def __call__(self, sample):
        image1, image2, image3, image4, image5, y = (
            sample["image1"],
            sample["image2"],
            sample["image3"],
            sample["image4"],
            sample["image5"],
            sample["y"],
        )

        # swap color axis because
        # numpy image: H x W x C
        # torch image: C X H X W
        image1 = image1.transpose((2, 0, 1))
        image2 = image2.transpose((2, 0, 1))
        image3 = image3.transpose((2, 0, 1))
        image4 = image4.transpose((2, 0, 1))
        image5 = image5.transpose((2, 0, 1))
        return {
            "image1": torch.from_numpy(image1),
            "image2": torch.from_numpy(image2),
            "image3": torch.from_numpy(image3),
            "image4": torch.from_numpy(image4),
            "image5": torch.from_numpy(image5),
            "y": torch.tensor(y),
        }


class Normalize(object):
    """Normalize image"""

    transform = transforms.Normalize(
        mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
    )

    def __call__(self, sample):
        image1, image2, image3, image4, image5, y = (
            sample["image1"],
            sample["image2"],
            sample["image3"],
            sample["image4"],
            sample["image5"],
            sample["y"],
        )
        return {
            "image1": self.transform(image1 / 255.0),
            "image2": self.transform(image2 / 255.0),
            "image3": self.transform(image3 / 255.0),
            "image4": self.transform(image4 / 255.0),
            "image5": self.transform(image5 / 255.0),
            "y": y,
        }


def keys2controller(keys: int) -> np.ndarray:
    """
    Translate a keyboard input into a controller input
    Input:
        keys: integer representing keys pressed
    Output:
        np.ndarray [3] translated controller input
    """
    if keys == 1:
        return np.asarray([-1.0, -1.0, -1.0], dtype=np.float32)
    if keys == 2:
        return np.asarray([1.0, -1.0, -1.0], dtype=np.float32)
    if keys == 3:
        return np.asarray([0.0, -1.0, 1.0], dtype=np.float32)
    if keys == 4:
        return np.asarray([0.0, 1.0, -1.0], dtype=np.float32)
    if keys == 5:
        return np.asarray([-1.0, -1.0, 1.0], dtype=np.float32)
    if keys == 6:
        return np.asarray([-1.0, 1.0, -1.0], dtype=np.float32)
    if keys == 7:
        return np.asarray([1.0, -1.0, 1.0], dtype=np.float32)
    if keys == 8:
        return np.asarray([1.0, 1.0, -1.0], dtype=np.float32)
    return np.asarray([0.0, -1.0, -1.0], dtype=np.float32)


class Tedd1104Dataset(Dataset):
    """TEDD1104 dataset."""

    def __init__(
        self,
        dataset_dir: str,
        hide_map_prob: float,
        dropout_images_prob: List[float],
        keyboard_dataset: bool = False,
    ):
        """
        Init

        Input:
        -dataset_dir: Directory containing the dataset files
        -hide_map_prob: Probability for removing the minimap (black square)
          from the sequence of images (0<=hide_map_prob<=1)
        - dropout_images_prob List of 5 floats or None, probability for removing each input image during training
         (black image) from a training example (0<=dropout_images_prob<=1)
        -keyboard_dataset: Set this flag if dataset uses keyboard input (V2 dataset), the keys will be converted to
         controller input
        """

        assert 0 <= hide_map_prob <= 1.0, (
            f"hide_map_prob not in 0 <= hide_map_prob <= 1.0 range. "
            f"hide_map_prob: {hide_map_prob}"
        )

        assert len(dropout_images_prob) == 5, (
            f"dropout_images_prob must have 5 probabilities, one for each image in the sequence. "
            f"dropout_images_prob len: {len(dropout_images_prob)}"
        )

        for dropout_image_prob in dropout_images_prob:
            assert 0 <= dropout_image_prob <= 1.0, (
                f"All probabilities in dropout_image_prob must be in the range 0 <= dropout_image_prob <= 1.0. "
                f"dropout_images_prob: {dropout_images_prob}"
            )

        self.dataset_dir = dataset_dir
        self.hide_map_prob = hide_map_prob
        self.dropout_images_prob = dropout_images_prob
        self.keyboard_dataset = keyboard_dataset
        self.transform = transforms.Compose(
            [
                RemoveMinimap(hide_map_prob=hide_map_prob),
                RemoveImage(dropout_images_prob=dropout_images_prob),
                SplitImages(),
                ToTensor(),
                Normalize(),
            ]
        )
        self.dataset_files = glob.glob(os.path.join(dataset_dir, "*.jpeg"))

    def __len__(self):
        return len(self.dataset_files)

    def __getitem__(self, idx):

        if torch.is_tensor(idx):
            idx = idx.tolist()

        img_name = self.dataset_files[idx]
        image = None
        while image is None:
            try:
                image = io.imread(img_name)
            except (ValueError, FileNotFoundError) as err:
                error_message = str(err).split("\n")[-1]
                print(
                    f"Error reading image: {img_name} probably a corrupted file.\n"
                    f"Exception: {error_message}\n"
                    f"We will load a random image instead."
                )
                img_name = random.choice(self.dataset_files)

        if not self.keyboard_dataset:
            y = np.asarray(
                [
                    float(x)
                    for x in os.path.basename(img_name)[:-5].split("_")[-1].split(",")
                ],
                dtype=np.float32,
            )
        else:
            keys: int = int(os.path.basename(img_name)[-6])
            y = keys2controller(keys)

        sample = {"image": image, "y": y}

        return self.transform(sample)
