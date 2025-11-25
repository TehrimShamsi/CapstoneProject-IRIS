{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AnalysisOutput",
  "type": "object",
  "required": ["paper_id","claims","methods","datasets","metrics","limitations"],
  "properties": {
    "paper_id": {"type":"string"},
    "title": {"type":["string","null"]},
    "abstract_summary": {"type":["string","null"]},
    "claims": {
      "type":"array",
      "items": {
        "type":"object",
        "required":["claim_id","claim_text","claim_type","provenance","confidence"],
        "properties": {
          "claim_id":{"type":"string"},
          "claim_text":{"type":"string"},
          "claim_type":{"type":"string","enum":["result","hypothesis","observation"]},
          "provenance":{
            "type":"array",
            "items":{
              "type":"object",
              "required":["chunk_id","quote"],
              "properties": {
                "chunk_id":{"type":"string"},
                "start_offset":{"type":["integer","null"]},
                "end_offset":{"type":["integer","null"]},
                "quote":{"type":"string"}
              }
            }
          },
          "confidence":{"type":"number","minimum":0,"maximum":1}
        }
      }
    },
    "methods": {
      "type":"array",
      "items":{
        "type":"object",
        "required":["method_id","description","provenance","confidence"],
        "properties": {
          "method_id":{"type":"string"},
          "description":{"type":"string"},
          "provenance":{"type":"array"},
          "confidence":{"type":"number"}
        }
      }
    },
    "datasets": {
      "type":"array",
      "items":{
        "type":"object",
        "properties": {
          "name":{"type":"string"},
          "description":{"type":["string","null"]},
          "provenance":{"type":"array"}
        }
      }
    },
    "metrics": {
      "type":"array",
      "items":{
        "type":"object",
        "properties": {
          "name":{"type":"string"},
          "value":{"type":"string"},
          "context":{"type":["string","null"]},
          "provenance":{"type":"array"}
        }
      }
    },
    "limitations":{"type":"array"},
    "conclusion":{"type":["string","null"]}
  }
}
