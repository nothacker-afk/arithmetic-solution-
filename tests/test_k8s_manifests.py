"""Tests for Kubernetes + Helm manifests (Phase 20)."""
import os
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML required for manifest tests")


def _load_yaml(path: Path):
    with open(path) as f:
        return yaml.safe_load(f)


def test_k8s_namespace():
    doc = _load_yaml(Path("k8s/namespace.yaml"))
    assert doc["kind"] == "Namespace"
    assert doc["metadata"]["name"] == "arithmetic"


def test_k8s_deployment_has_probes():
    doc = _load_yaml(Path("k8s/deployment.yaml"))
    containers = doc["spec"]["template"]["spec"]["containers"]
    assert containers[0]["name"] == "api"
    assert "readinessProbe" in containers[0]
    assert "livenessProbe" in containers[0]
    assert containers[0]["readinessProbe"]["httpGet"]["path"] == "/api/health"


def test_k8s_service():
    doc = _load_yaml(Path("k8s/service.yaml"))
    assert doc["kind"] == "Service"
    assert doc["spec"]["selector"]["app"] == "arithmetic-api"


def test_k8s_ingress_websocket_annotation():
    doc = _load_yaml(Path("k8s/ingress.yaml"))
    ann = doc["metadata"]["annotations"]
    assert "websocket" in ann.get("nginx.ingress.kubernetes.io/websocket-services", "").lower() or \
           "arithmetic-api" in ann.get("nginx.ingress.kubernetes.io/websocket-services", "")


def test_helm_chart_yaml():
    doc = _load_yaml(Path("helm/arithmetic/Chart.yaml"))
    assert doc["name"] == "arithmetic"
    assert doc["apiVersion"] == "v2"
    assert doc["version"] == "0.21.0"


def test_helm_values():
    doc = _load_yaml(Path("helm/arithmetic/values.yaml"))
    assert doc["replicaCount"] >= 1
    assert "image" in doc
    assert "ingress" in doc
    assert "persistence" in doc


def test_helm_templates_exist():
    templates_dir = Path("helm/arithmetic/templates")
    expected = {
        "_helpers.tpl", "deployment.yaml", "service.yaml",
        "ingress.yaml", "secret.yaml", "configmap.yaml",
        "pvc.yaml", "NOTES.txt",
    }
    present = {p.name for p in templates_dir.iterdir()}
    missing = expected - present
    assert not missing, f"Missing templates: {missing}"


def test_k8s_files_exist():
    for name in ("namespace.yaml", "configmap.yaml", "secret.yaml.example",
                 "pvc.yaml", "deployment.yaml", "service.yaml", "ingress.yaml"):
        assert Path(f"k8s/{name}").exists(), f"Missing k8s/{name}"
