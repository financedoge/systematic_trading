from systematic_trading.config import AppSettings
from systematic_trading.data.providers import ProviderRegistry
from systematic_trading.data.tushare import TushareUsDailyProvider, read_tushare_token


def test_tushare_token_reader_uses_plaintext_file(tmp_path) -> None:
    token_path = tmp_path / "tushare_token.txt"
    token_path.write_text(" secret-token \n", encoding="utf-8")

    assert read_tushare_token(token_path) == "secret-token"


def test_provider_registry_marks_tushare_configured_from_token_file(tmp_path) -> None:
    token_path = tmp_path / "tushare_token.txt"
    token_path.write_text("secret-token", encoding="utf-8")
    settings = AppSettings(tushare_token_path=token_path)

    manifests = {manifest.source_id: manifest for manifest in ProviderRegistry(settings).manifests()}

    assert manifests["tushare"].configured is True
    assert "US" in manifests["tushare"].regions


def test_tushare_provider_is_optional_until_fetch_time(tmp_path) -> None:
    token_path = tmp_path / "tushare_token.txt"
    token_path.write_text("secret-token", encoding="utf-8")

    provider = TushareUsDailyProvider(token_path=token_path)

    assert provider.manifest.configured is True
    assert provider.adjusted is True
