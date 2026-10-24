"""Load the HA-independent protocol modules without importing the HA package."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "govee_h7140_ble"

package = types.ModuleType("govee_h7140_ble")
package.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
sys.modules["govee_h7140_ble"] = package

for module_name in ("const", "protocol", "encryption"):
    spec = importlib.util.spec_from_file_location(
        f"govee_h7140_ble.{module_name}", ROOT / f"{module_name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"govee_h7140_ble.{module_name}"] = module
    spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def _mock_bluetooth_setup():
    """Avoid setting up BlueZ/D-Bus on non-Linux test hosts."""
    with patch("homeassistant.components.bluetooth.async_setup", return_value=True):
        yield
