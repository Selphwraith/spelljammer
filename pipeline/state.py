"""Pipeline state management — persists to game-launch/launch-manifest.json."""
import json
from datetime import datetime
from pathlib import Path

STAGES = ["dev", "marketing", "store_setup", "deploy"]


class PipelineState:
    def __init__(self, game_path: str):
        self.game_path = Path(game_path)
        self.manifest_path = self.game_path / "game-launch" / "launch-manifest.json"
        self._data = self._default_data()

    # ─── default schema ────────────────────────────────────────────────────────

    def _default_data(self) -> dict:
        now = datetime.now().isoformat()
        return {
            "version": "1.0.0",
            "created_at": now,
            "updated_at": now,
            "game_path": str(self.game_path),
            "current_stage": "dev",
            "game_info": {
                "name": "",
                "description": "",
                "main_file": None,
                "file_count": 0,
                "size_bytes": 0,
                "file_types": [],
            },
            "stages": {
                "dev": {"status": "in_progress", "completed_at": None},
                "marketing": {"status": "pending", "completed_at": None},
                "store_setup": {"status": "pending", "completed_at": None},
                "deploy": {"status": "pending", "completed_at": None},
            },
            "marketing": {
                "store_listing": {"variants": [], "selected_index": 0, "final_text": ""},
                "social_media": {"variants": [], "selected_index": 0, "final_text": ""},
                "press_release": {"variants": [], "selected_index": 0, "final_text": ""},
                "key_art": {"variants": [], "selected_index": 0, "final_text": ""},
            },
            "store_configs": {
                "itch_io": {"content": "", "approved": False},
                "steam": {"content": "", "approved": False},
                "analytics": {"content": "", "approved": False},
            },
        }

    # ─── persistence ───────────────────────────────────────────────────────────

    def load(self) -> bool:
        if not self.manifest_path.exists():
            return False
        try:
            with open(self.manifest_path) as f:
                loaded = json.load(f)
            self._deep_merge(self._data, loaded)
            return True
        except Exception:
            return False

    def save(self) -> None:
        self._data["updated_at"] = datetime.now().isoformat()
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w") as f:
            json.dump(self._data, f, indent=2)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                PipelineState._deep_merge(base[k], v)
            else:
                base[k] = v

    # ─── accessors ─────────────────────────────────────────────────────────────

    @property
    def current_stage(self) -> str:
        return self._data["current_stage"]

    @property
    def game_info(self) -> dict:
        return self._data["game_info"]

    @property
    def stages(self) -> dict:
        return self._data["stages"]

    @property
    def marketing(self) -> dict:
        return self._data["marketing"]

    @property
    def store_configs(self) -> dict:
        return self._data["store_configs"]

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    # ─── mutations ─────────────────────────────────────────────────────────────

    def update_game_info(self, info: dict) -> None:
        self._data["game_info"].update(info)
        self.save()

    def complete_stage(self, stage: str) -> None:
        self._data["stages"][stage]["status"] = "complete"
        self._data["stages"][stage]["completed_at"] = datetime.now().isoformat()
        idx = STAGES.index(stage)
        if idx + 1 < len(STAGES):
            nxt = STAGES[idx + 1]
            self._data["current_stage"] = nxt
            self._data["stages"][nxt]["status"] = "in_progress"
        self.save()

    def update_marketing_variants(self, content_type: str, variants: list) -> None:
        self._data["marketing"][content_type]["variants"] = variants
        self.save()

    def set_marketing_selection(self, content_type: str, idx: int, text: str) -> None:
        self._data["marketing"][content_type]["selected_index"] = idx
        self._data["marketing"][content_type]["final_text"] = text
        self.save()

    def set_store_config(self, config_type: str, content: str, approved: bool = False) -> None:
        self._data["store_configs"][config_type]["content"] = content
        self._data["store_configs"][config_type]["approved"] = approved
        self.save()

    def all_marketing_complete(self) -> bool:
        return all(
            self._data["marketing"][ct]["final_text"]
            for ct in ("store_listing", "social_media", "press_release", "key_art")
        )

    def all_configs_approved(self) -> bool:
        return all(
            self._data["store_configs"][ct]["approved"]
            for ct in ("itch_io", "steam", "analytics")
        )

    def to_dict(self) -> dict:
        return self._data
