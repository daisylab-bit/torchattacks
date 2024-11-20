from typing import Callable, Self

import torch
import torch.nn as nn


class AttackModel:
    """A wrapper class for a pretrained model used for adversarial attacks.

    Intended to be instantiated with
    `AttackModel.from_pretrained(pretrained_model_name)` from either
    `torchvision.models` or `timm`. The model is loaded and attributes including
    `transform`, `normalize`, and `model_name` are attached based on the model's
    configuration.

    Attributes:
        model_name (str): The name of the model.
        device (torch.device): The device on which the model is loaded.
        model (nn.Module): The pretrained model itself.
        transform (Callable): The transformation function applied to input images.
        normalize (Callable): The normalization function applied to input images.

    Example:
        >>> model = AttackModel.from_pretrained('resnet50', device='cuda')
        >>> model
        AttackModel(model_name=resnet50, device=cuda, transform=Compose(...), normalize=Normalize(...))
        >>> model.transform
        Compose(
            Resize(size=[256], interpolation=bilinear, max_size=None, antialias=True)
            CenterCrop(size=(224, 224))
            ToTensor()
        )
        >>> model.normalize
        Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        >>> model.model
        ResNet(
            (conv1): Conv2d(3, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
            ...
        )
    """

    def __init__(
        self,
        model_name: str,
        device: torch.device,
        model: nn.Module,
        transform: Callable,
        normalize: Callable,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.model = model
        self.transform = transform
        self.normalize = normalize

    @classmethod
    def from_pretrained(
        cls,
        model_name: str,
        device: torch.device,
        from_timm: bool = False,
    ) -> Self:
        """
        Loads a pretrained model and initializes an AttackModel instance.

        Args:
            model_name: The name of the model to load.
            device: The device on which to load the model.
            from_timm: Whether to load the model from timm. Defaults to False.

        Returns:
            AttackModel: An instance of AttackModel initialized with pretrained model.
        """

        import torchvision.transforms as t

        if from_timm:
            import timm

            model = timm.create_model(model_name, pretrained=True)
            model = model.to(device).eval()
            cfg = timm.data.resolve_data_config(model.pretrained_cfg)

            # Construct normalization
            normalize = t.Normalize(mean=cfg['mean'], std=cfg['std'])

            # Create a transform based on the model pretrained cfg
            transform = timm.data.create_transform(**cfg, is_training=False)
            # Remove the Normalize from composed transform if there is one
            transform.transforms = [
                tr for tr in transform.transforms if not isinstance(tr, t.Normalize)
            ]

            return cls(model_name, device, model, transform, normalize)

        # If the model is not specified to be load from timm, try loading from
        # `torchvision.models` first, then fall back to timm if the model is not found.
        try:
            import torchvision.models as tv_models

            model = tv_models.get_model(name=model_name, weights='DEFAULT')
            model = model.to(device).eval()

            # Resolve transforms from vision model weights
            weight_id = str(tv_models.get_model_weights(name=model_name)['DEFAULT'])
            cfg = tv_models.get_weight(weight_id).transforms()

            # torchvision/transforms/_presets.py::ImageClassification
            # Manually construct separated transform and normalize
            transform = t.Compose(
                [
                    t.Resize(
                        cfg.resize_size,
                        interpolation=cfg.interpolation,
                        antialias=cfg.antialias,
                    ),
                    t.CenterCrop(cfg.crop_size),
                    t.ToTensor(),
                ]
            )
            normalize = t.Normalize(mean=cfg.mean, std=cfg.std)

            return cls(model_name, device, model, transform, normalize)

        except ValueError:
            print(
                f'Warning: Model `{model_name}` not found in torchvision.models, '
                'falling back to loading weights from timm.'
            )
            return cls.from_pretrained(model_name, device, from_timm=True)

    def forward(self, x):
        return self.model(x)

    def __call__(self, x):
        return self.forward(x)

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'model_name={self.model_name}, '
            f'device={self.device}, '
            f'transform={self.transform}, '
            f'normalize={self.normalize})'
        )