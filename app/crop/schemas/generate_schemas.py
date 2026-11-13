"""JSON Schema generator for all crop plan Pydantic models.

Generates JSON Schema from Pydantic models and writes them to the
schemas directory. Can be run standalone to regenerate schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.crop.models.project_profile import ProjectTrimProfile
from app.crop.models.crop_region import CropRegion
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus


# Map of model names to their classes
SCHEMA_MODELS: dict[str, type] = {
    "ProjectTrimProfile": ProjectTrimProfile,
    "CropRegion": CropRegion,
    "PageCropPlan": PageCropPlan,
    "CropValidationResult": CropValidationResult,
    "DocumentCropPlan": DocumentCropPlan,
    "DocumentStatus": DocumentStatus,
}


def generate_schema(model_class: type) -> dict:
    """Generate JSON Schema from a Pydantic model class."""
    return model_class.model_json_schema()


def generate_all_schemas() -> dict[str, dict]:
    """Generate JSON Schemas for all crop plan models."""
    return {
        name: generate_schema(cls)
        for name, cls in SCHEMA_MODELS.items()
    }


def write_schemas_to_directory(output_dir: Path | str) -> list[Path]:
    """Write all JSON Schemas to individual files in the output directory.

    Returns list of paths to the written schema files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for name, schema in generate_all_schemas().items():
        filename = f"{name}.schema.json"
        filepath = output_dir / filename
        filepath.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written.append(filepath)

    return written


if __name__ == "__main__":
    # Generate schemas to the schemas directory
    schema_dir = Path(__file__).parent
    written = write_schemas_to_directory(schema_dir)
    for path in written:
        print(f"Written: {path}")

