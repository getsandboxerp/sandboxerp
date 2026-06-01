"""
Tests for sandboxerp.engine.docker and sandboxerp.docker.templates.

All Docker API calls are mocked; no real Docker daemon is required.

:author: Hector Colina / Team360 <https://team360.cl>
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sandboxerp.docker.templates import (
    ComposeTemplate,
    ServiceTemplate,
    build_odoo_template,
)
from sandboxerp.engine.docker import (
    LABEL_KEY,
    LABEL_VALUE,
    create_database,
    generate_compose,
    image_exists,
    is_docker_running,
    write_compose,
)


# ─────────────────────────────────────────
# engine/docker.py tests
# ─────────────────────────────────────────


class TestIsDockerRunning:
    def test_returns_true_when_daemon_responds(self):
        with patch("sandboxerp.engine.docker.docker.from_env") as mock_env:
            mock_client = MagicMock()
            mock_env.return_value = mock_client
            assert is_docker_running() is True

    def test_returns_false_when_daemon_unreachable(self):
        import docker.errors

        with patch("sandboxerp.engine.docker.docker.from_env") as mock_env:
            mock_env.side_effect = docker.errors.DockerException("not running")
            assert is_docker_running() is False


class TestImageExists:
    def test_returns_true_when_image_found(self):
        mock_client = MagicMock()
        assert image_exists(mock_client, "odoo:17") is True

    def test_returns_false_when_image_missing(self):
        import docker.errors

        mock_client = MagicMock()
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        assert image_exists(mock_client, "odoo:17") is False


class TestGenerateCompose:
    def test_contains_odoo_image(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
        )
        assert "odoo:17" in yaml_str

    def test_contains_postgres_image(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
        )
        assert "postgres:15" in yaml_str

    def test_contains_sandbox_label(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
        )
        assert LABEL_KEY in yaml_str
        assert LABEL_VALUE in yaml_str

    def test_custom_port_appears_in_output(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
            port=8888,
        )
        assert "8888" in yaml_str

    def test_custom_bind_appears_in_output(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
            bind="0.0.0.0",
        )
        assert "0.0.0.0" in yaml_str

    def test_seed_appears_in_output(self):
        yaml_str = generate_compose(
            project_name="test",
            country="cl",
            industry="retail",
            profile="small",
            seed=1234,
        )
        assert "1234" in yaml_str


class TestWriteCompose:
    def test_file_is_created(self, tmp_path: Path):
        yaml_str = "version: '3.8'\nservices: {}\n"
        result = write_compose(yaml_str, tmp_path)
        assert result.exists()
        assert result.name == "docker-compose.yml"

    def test_file_content_matches(self, tmp_path: Path):
        yaml_str = "version: '3.8'\nservices: {}\n"
        result = write_compose(yaml_str, tmp_path)
        assert result.read_text() == yaml_str

    def test_creates_missing_directory(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "c"
        write_compose("content", nested)
        assert (nested / "docker-compose.yml").exists()


# ─────────────────────────────────────────
# docker/templates.py tests
# ─────────────────────────────────────────


class TestServiceTemplate:
    def test_to_dict_contains_image(self):
        svc = ServiceTemplate(name="db", image="postgres:15")
        d = svc.to_dict()
        assert d["image"] == "postgres:15"

    def test_to_dict_omits_empty_fields(self):
        svc = ServiceTemplate(name="db", image="postgres:15")
        d = svc.to_dict()
        assert "ports" not in d
        assert "depends_on" not in d
        assert "environment" not in d

    def test_to_dict_includes_labels(self):
        svc = ServiceTemplate(
            name="db", image="postgres:15", labels={"sandboxerp": "true"}
        )
        d = svc.to_dict()
        assert d["labels"] == {"sandboxerp": "true"}


class TestComposeTemplate:
    def test_render_contains_services(self):
        tmpl = ComposeTemplate(
            services=[ServiceTemplate(name="db", image="postgres:15")]
        )
        rendered = tmpl.render()
        assert "db" in rendered
        assert "postgres:15" in rendered

    def test_render_includes_header_comment(self):
        tmpl = ComposeTemplate(
            services=[ServiceTemplate(name="db", image="postgres:15")],
            header_comment="Generated by SandboxERP",
        )
        rendered = tmpl.render()
        assert rendered.startswith("# Generated by SandboxERP")

    def test_render_includes_named_volumes(self):
        tmpl = ComposeTemplate(
            services=[ServiceTemplate(name="db", image="postgres:15")],
            named_volumes=["db_data"],
        )
        rendered = tmpl.render()
        assert "db_data" in rendered


class TestBuildOdooTemplate:
    def test_returns_compose_template(self):
        tmpl = build_odoo_template(
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
        )
        assert isinstance(tmpl, ComposeTemplate)

    def test_has_two_services(self):
        tmpl = build_odoo_template(
            country="cl", industry="retail", profile="small", seed=42
        )
        assert len(tmpl.services) == 2

    def test_odoo_service_uses_correct_version(self):
        tmpl = build_odoo_template(
            country="cl", industry="retail", profile="small", seed=42, odoo_version="16"
        )
        odoo_svc = next(s for s in tmpl.services if s.name == "odoo")
        assert odoo_svc.image == "odoo:16"

    def test_country_label_is_set(self):
        tmpl = build_odoo_template(
            country="mx", industry="retail", profile="small", seed=42
        )
        for svc in tmpl.services:
            assert svc.labels.get("sandboxerp.country") == "mx"

    def test_render_contains_bind_and_port(self):
        tmpl = build_odoo_template(
            country="cl",
            industry="retail",
            profile="small",
            seed=42,
            bind="0.0.0.0",
            port=8888,
        )
        rendered = tmpl.render()
        assert "0.0.0.0" in rendered
        assert "8888" in rendered


# ─────────────────────────────────────────
# create_database tests
# ─────────────────────────────────────────


class TestCreateDatabase:
    """Tests for create_database() — all HTTP calls are mocked."""

    def test_returns_on_success(self):
        """A result=True response resolves immediately."""
        with patch("sandboxerp.engine.docker.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {"result": True}
            create_database(timeout=10, interval=0)
            mock_post.assert_called_once()

    def test_returns_if_db_already_exists(self):
        """An 'already exists' error is treated as success."""
        with patch("sandboxerp.engine.docker.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "error": {
                    "data": {"message": "database already exists"}
                }
            }
            create_database(timeout=10, interval=0)
            mock_post.assert_called_once()

    def test_retries_on_transient_error(self):
        """Network errors trigger retries until success."""
        responses = [
            Exception("connection refused"),
            Exception("connection refused"),
            MagicMock(**{"json.return_value": {"result": True}}),
        ]
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            r = responses[call_count]
            call_count += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch("sandboxerp.engine.docker.httpx.post", side_effect=side_effect):
            create_database(timeout=30, interval=0)

        assert call_count == 3

    def test_raises_on_timeout(self):
        """RuntimeError is raised if the database is never created."""
        with patch("sandboxerp.engine.docker.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "error": {"data": {"message": "some unrecoverable error"}}
            }
            with pytest.raises(RuntimeError, match="Could not create Odoo database"):
                create_database(timeout=0, interval=0)

    def test_posts_to_correct_url(self):
        """The request targets /web/database/create on the given host/port."""
        with patch("sandboxerp.engine.docker.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {"result": True}
            create_database(host="10.0.0.1", port=8080, timeout=10, interval=0)
            url = mock_post.call_args[0][0]
            assert url == "http://10.0.0.1:8080/web/database/create"

    def test_payload_contains_db_name(self):
        """The JSON payload includes the requested database name."""
        with patch("sandboxerp.engine.docker.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {"result": True}
            create_database(db_name="mydb", timeout=10, interval=0)
            payload = mock_post.call_args[1]["json"]
            assert payload["params"]["name"] == "mydb"
