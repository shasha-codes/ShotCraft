"""Minimal ShotCraft Strands setup check."""

from strands import Agent
from strands.models import BedrockModel


def main() -> None:
    # Disable Strands' streaming console callback so this smoke test prints one
    # clean result, which is easier to read in terminal and CI logs.
    agent = Agent(
        model=BedrockModel(model_id="google.gemma-3-4b-it"),
        callback_handler=None,
    )
    response = agent("In one sentence, describe a soft editorial portrait shoot.")
    print(response)


if __name__ == "__main__":
    main()
