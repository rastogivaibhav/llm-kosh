class AiCartridge < Formula
  desc "LlmKosh - Portable memory storage for LLMs"
  homepage "https://github.com/rastogivaibhav/ai_memory_cartridge"
  url "https://github.com/rastogivaibhav/ai_memory_cartridge/releases/download/v1.0.0/cartridge-mac.tar.gz"
  sha256 "REPLACE_WITH_SHA256"
  version "1.0.0"

  def install
    bin.install "cartridge"
  end

  test do
    system "#{bin}/cartridge", "--help"
  end
end
