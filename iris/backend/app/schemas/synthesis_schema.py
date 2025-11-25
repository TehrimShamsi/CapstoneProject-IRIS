{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SynthesisOutput",
  "type": "object",
  "required": ["topic","executive_summary","comparison_table","consensus_statements","contradictions","gaps_and_research_directions","recommendations_for_practitioners","confidence_overall"],
  "properties": {
    "topic":{"type":"string"},
    "executive_summary":{"type":"string"},
    "comparison_table":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "paper_id":{"type":"string"},
          "methods":{"type":"string"},
          "datasets":{"type":"string"},
          "key_results":{"type":"string"},
          "notes":{"type":"string"}
        }
      }
    },
    "consensus_statements":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "statement":{"type":"string"},
          "supporting_claims":{
            "type":"array",
            "items":{"type":"object","properties":{"paper_id":{"type":"string"},"claim_id":{"type":"string"}}}
          },
          "confidence":{"type":"number"}
        }
      }
    },
    "contradictions":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "description":{"type":"string"},
          "paper_pairs":{"type":"array"},
          "confidence":{"type":"number"}
        }
      }
    },
    "gaps_and_research_directions":{"type":"array"},
    "recommendations_for_practitioners":{"type":"array"},
    "confidence_overall":{"type":"number"}
  }
}
