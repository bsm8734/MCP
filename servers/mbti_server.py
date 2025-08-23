########################################
# servers/mbti_server.py (MBTI 성향 전용)
########################################
from fastmcp import FastMCP
from FinalProject.schemas import MBTIInput, MBTITraits
from utils.style import MBTI_TRAIT_MAP

app = FastMCP("mbti-mcp")


@app.tool()
def infer_mbti_traits(input: MBTIInput) -> MBTITraits:
    traits = MBTI_TRAIT_MAP.get(input.mbti, ["균형"])
    return MBTITraits(traits=traits, summary=", ".join(traits))


if __name__ == "__main__":
    app.run()