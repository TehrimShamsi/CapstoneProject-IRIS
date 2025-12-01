from app.agents.synthesis_agent import SynthesisAgent

# Create two analyses with overlapping claims
analyses = [
    {
        "paper_id": "paper:A",
        "claims": [
            {"claim_id": "A_c1", "text": "Our method improves accuracy by 5%", "confidence": 0.8},
            {"claim_id": "A_c2", "text": "We use a Transformer-based encoder", "confidence": 0.6}
        ]
    },
    {
        "paper_id": "paper:B",
        "claims": [
            {"claim_id": "B_c1", "text": "Accuracy improved by 5 percent in our experiments", "confidence": 0.7},
            {"claim_id": "B_c2", "text": "We don't observe improvement", "confidence": 0.4}
        ]
    }
]

agent = SynthesisAgent(model_name=None)
res = agent.synthesize(analyses)
import json
print(json.dumps(res, indent=2))
