# region MODULE_CONTRACT [DOMAIN(6): Testing; CONCEPT(7): GradioPatch; TECH(7): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

from pathlib import Path


def test_gradio_vlm_preset_patch_script_has_inject_contract():
    path = (
        Path(__file__).resolve().parents[1]
        / "deploy"
        / "docling-serve"
        / "apply_gradio_vlm_preset_patch.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "vlm_pipeline_preset" in text
    assert 'parameters["options"]["vlm_pipeline_preset"] = "default"' in text
    assert 'str(pipeline) == "vlm"' in text


def test_dockerfile_applies_gradio_and_app_patches():
    path = (
        Path(__file__).resolve().parents[1]
        / "deploy"
        / "docling-serve"
        / "Dockerfile"
    )
    text = path.read_text(encoding="utf-8")
    assert "apply_gradio_vlm_preset_patch.py" in text
    assert "apply_app_vlm_middleware_patch.py" in text
    assert "vlm_preset_middleware.py" in text
    assert "VLM preset patches verified" in text


def test_vlm_preset_middleware_contract():
    path = (
        Path(__file__).resolve().parents[1]
        / "deploy"
        / "docling-serve"
        / "vlm_preset_middleware.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "class VlmPresetInjectMiddleware" in text
    assert 'vlm_pipeline_preset"] = "default"' in text or 'vlm_pipeline_preset"] = "default"' in text.replace("'", '"')
    assert 'options["vlm_pipeline_preset"] = "default"' in text
