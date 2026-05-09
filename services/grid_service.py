import rag_manager
from grid_mapping_agent import extract_grid_data


def save_feedback(context: str, correction: str):
    rag_manager.add_feedback(context, correction)
    return {
        "status": "success",
        "message": "Feedback securely saved to AI Memory for future analyses.",
    }


def save_grid_intelligence(substation_name: str, intelligence_text: str):
    rag_manager.add_grid_intelligence(substation_name, intelligence_text)
    return {
        "status": "success",
        "message": f"Intelligence for {substation_name} embedded in proprietary vault.",
    }


def extract_and_store_grid_data(text: str):
    return extract_grid_data(text)


def get_structured_substations():
    return rag_manager.retrieve_all_structured_gss_data()
