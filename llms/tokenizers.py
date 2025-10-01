import os
from typing import Any

import tiktoken
from transformers import LlamaTokenizer, AutoTokenizer  # type: ignore


class Tokenizer(object):
    def __init__(self, provider: str, model_name: str) -> None:
        if provider == "openai":
            if "Llama-3" in model_name:
                assert "OPENAI_API_BASE" in os.environ
                self.tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")
            elif "gpt-oss" in model_name:
                # https://github.com/openai/gpt-oss/blob/7802bf263f902efd4c7d18fcceff3ba72f941e80/gpt_oss/tokenizer.py
                o200k_base = tiktoken.get_encoding("o200k_base")
                tokenizer = tiktoken.Encoding(
                    name="o200k_harmony",
                    pat_str=o200k_base._pat_str,
                    mergeable_ranks=o200k_base._mergeable_ranks,
                    special_tokens={
                        **o200k_base._special_tokens,
                        "<|startoftext|>": 199998,
                        "<|endoftext|>": 199999,
                        "<|reserved_200000|>": 200000,
                        "<|reserved_200001|>": 200001,
                        "<|return|>": 200002,
                        "<|constrain|>": 200003,
                        "<|reserved_200004|>": 200004,
                        "<|channel|>": 200005,
                        "<|start|>": 200006,
                        "<|end|>": 200007,
                        "<|message|>": 200008,
                        "<|reserved_200009|>": 200009,
                        "<|reserved_200010|>": 200010,
                        "<|reserved_200011|>": 200011,
                        "<|call|>": 200012,
                    } | {
                        f"<|reserved_{i}|>": i for i in range(200013, 201088)
                    },
                )
                self.tokenizer = tokenizer
            else:
                self.tokenizer = tiktoken.encoding_for_model(model_name)
        elif provider == "huggingface":
            self.tokenizer = LlamaTokenizer.from_pretrained(model_name)
            # turn off adding special tokens automatically
            self.tokenizer.add_special_tokens = False  # type: ignore[attr-defined]
            self.tokenizer.add_bos_token = False  # type: ignore[attr-defined]
            self.tokenizer.add_eos_token = False  # type: ignore[attr-defined]
        elif provider == "google":
            self.tokenizer = None  # Not used for input length computation, as Gemini is based on characters
        else:
            raise NotImplementedError

    def encode(self, text: str) -> list[int]:
        return self.tokenizer.encode(text)

    def decode(self, ids: list[int]) -> str:
        return self.tokenizer.decode(ids)

    def __call__(self, text: str) -> list[int]:
        return self.tokenizer.encode(text)
