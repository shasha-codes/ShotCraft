"""Minimal ShotCraft Strands setup check."""

from strands import Agent


def main() -> None:
    agent = Agent()
    response = agent("In one sentence, describe a soft editorial portrait shoot.")
    print(response)


if __name__ == "__main__":
    main()
