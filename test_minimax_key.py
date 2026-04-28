#!/usr/bin/env python3
"""Test MiniMax API key validity.

Usage:
    conda activate reachy_mini_env
    cd /path/to/clawbody-minimax
    python test_minimax_key.py

Tests multiple configurations to diagnose 401 errors.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def test_key(api_key: str, base_url: str, label: str) -> bool:
    """Test a specific key + base_url combination."""
    logger.info("Testing %s...", label)
    logger.info("  Key: %s...", api_key[:30] if len(api_key) > 30 else api_key)
    logger.info("  URL: %s", base_url)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        response = await client.chat.completions.create(
            model="MiniMax-M2.7",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
        )
        text = response.choices[0].message.content
        logger.info("  SUCCESS! Response: %s", text)
        return True

    except Exception as e:
        logger.error("  FAILED: %s", e)
        return False


async def main():
    """Run MiniMax key diagnostics."""
    logger.info("=" * 60)
    logger.info("MiniMax API Key Diagnostic Tool")
    logger.info("=" * 60)
    logger.info("")

    # Get key from env
    api_key = os.getenv("MINIMAX_API_KEY", "")
    if not api_key:
        logger.error("MINIMAX_API_KEY not found in .env")
        return

    logger.info("Key from .env: %s... (length: %d)", api_key[:30], len(api_key))
    logger.info("")

    # Test different base URLs
    test_configs = [
        (api_key, "https://api.minimaxi.chat/v1/", "Default URL (.env)"),
        (api_key, "https://api.minimaxi.chat/v1", "Without trailing slash"),
        (api_key, "https://api.minimax.chat/v1/", "Alternative spelling (minimax)"),
        (api_key, "https://api.minimax.chat/v1", "Alternative spelling, no slash"),
    ]

    results = []
    for key, url, label in test_configs:
        results.append((label, await test_key(key, url, label)))
        logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    for label, success in results:
        status = "PASS" if success else "FAIL"
        logger.info("%s: %s", status, label)

    any_success = any(r[1] for r in results)
    if not any_success:
        logger.info("")
        logger.info("All configurations failed. Possible causes:")
        logger.info("1. API key is invalid or expired")
        logger.info("2. Key was copied incorrectly (check for extra spaces or missing characters)")
        logger.info("3. Account doesn't have API access enabled")
        logger.info("4. Key format changed (MiniMax may use different prefixes now)")
        logger.info("")
        logger.info("Please verify your key at: https://www.minimaxi.chat/")


if __name__ == "__main__":
    asyncio.run(main())
