class LlmKosh < Formula
  include Language::Python::Virtualenv

  desc "Local-first AI memory cartridge with temporal causal reasoning for Claude and any LLM"
  homepage "https://github.com/rastogivaibhav/llm-kosh"
  url "https://github.com/rastogivaibhav/llm-kosh/archive/refs/tags/v2.1.1.tar.gz"
  sha256 "26be107fa036a79d035ec60e74f80b5f644a62cdbfe6af45f62e0a7ccf6b2e8e"
  license "MIT"
  version "2.1.1"

  depends_on "python@3.11"

  # Core optional extras — MCP server + file ingestion
  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/source/f/fastapi/fastapi-0.116.0.tar.gz"
    sha256 "" # populated by `brew audit --new-formula llm-kosh`
  end

  resource "mcp" do
    url "https://files.pythonhosted.org/packages/source/m/mcp/mcp-1.26.0.tar.gz"
    sha256 ""
  end

  def install
    virtualenv_install_with_resources

    # Run one-shot install: cartridge init, Claude Desktop config, PATH check
    system bin/"llm-kosh", "install", "--yes"
  end

  def post_install
    ohai "llm-kosh installed!"
    ohai "Start the service:  llm-kosh service start"
    ohai "Quick capture:     Ctrl+Shift+Space  (requires desktop app)"
  end

  test do
    assert_match "llm-kosh", shell_output("#{bin}/llm-kosh --help")
    assert_match "mcp-server", shell_output("#{bin}/llm-kosh --help")
  end
end
