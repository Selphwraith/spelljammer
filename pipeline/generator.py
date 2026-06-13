"""Output file generator — saves approved copy and configs into game-launch/."""
import json
from pathlib import Path


def fmt_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


class FileGenerator:
    def __init__(self, game_path: str):
        self.game_path = Path(game_path)
        self.launch_path = self.game_path / "game-launch"
        self.marketing_path = self.launch_path / "marketing"
        self.configs_path = self.launch_path / "configs"

    def ensure_dirs(self) -> None:
        self.marketing_path.mkdir(parents=True, exist_ok=True)
        self.configs_path.mkdir(parents=True, exist_ok=True)

    def save_all(self, state_data: dict) -> list[str]:
        self.ensure_dirs()
        saved: list[str] = []

        mkt = state_data.get("marketing", {})
        _mkt_files = {
            "store_listing": "store-listing.txt",
            "social_media": "social-media.txt",
            "press_release": "press-release.txt",
            "key_art": "key-art-descriptions.txt",
        }
        for key, fname in _mkt_files.items():
            text = mkt.get(key, {}).get("final_text", "")
            if text:
                p = self.marketing_path / fname
                p.write_text(text, encoding="utf-8")
                saved.append(str(p.relative_to(self.game_path)))

        sc = state_data.get("store_configs", {})
        if sc.get("itch_io", {}).get("content"):
            p = self.configs_path / "itch-io-config.json"
            p.write_text(sc["itch_io"]["content"], encoding="utf-8")
            saved.append(str(p.relative_to(self.game_path)))

        if sc.get("steam", {}).get("content"):
            p = self.configs_path / "steam-config.json"
            p.write_text(sc["steam"]["content"], encoding="utf-8")
            saved.append(str(p.relative_to(self.game_path)))

        if sc.get("analytics", {}).get("content"):
            p = self.configs_path / "analytics-setup.js"
            p.write_text(sc["analytics"]["content"], encoding="utf-8")
            saved.append(str(p.relative_to(self.game_path)))

        return saved

    def output_size(self) -> int:
        total = 0
        if self.launch_path.exists():
            for f in self.launch_path.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
        return total

    def list_output_files(self) -> list[str]:
        if not self.launch_path.exists():
            return []
        return sorted(
            str(f.relative_to(self.game_path))
            for f in self.launch_path.rglob("*")
            if f.is_file()
        )
