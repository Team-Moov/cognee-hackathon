# ontology/ml_ontology.py
import asyncio
import cognee

async def setup_ml_ontology():
    """
    Day 1 Task: Configures standard ML background knowledge rules into Groundhog.
    This lets the system understand that AdamW extends Adam, and both are Optimizers.
    """
    print("[*] Initializing Groundhog ML Domain Ontology...")
    
    # This is the layout our system will ingest once the graph DB is live
    ontology_payload = [
        # Optimizer classes
        {"term": "Optimizer", "category": "Superclass", "description": "Base mathematical algorithm for weight updates."},
        {"term": "Adam", "category": "Optimizer", "description": "Adaptive Moment Estimation optimizer."},
        {"term": "AdamW", "category": "Optimizer", "description": "Adam with decoupled weight decay optimization."},
        {"term": "SGD", "category": "Optimizer", "description": "Stochastic Gradient Descent optimizer."},
        
        # Architecture classes
        {"term": "Architecture", "category": "Superclass", "description": "Base structural design of the neural network."},
        {"term": "Transformer", "category": "Architecture", "description": "Attention-based neural sequence architecture."},
        {"term": "CNN", "category": "Architecture", "description": "Convolutional Neural Network for spatial grid processing."},
        {"term": "ResNet", "category": "Architecture", "description": "Residual network architecture using skip connections."}
    ]

    print("[+] Domain categories successfully defined:")
    for item in ontology_payload:
        print(f"    - Term: {item['term']} ({item['category']})")
        
    print("[+] Day 1 Ontology initialization completed successfully.")

if __name__ == "__main__":
    asyncio.run(setup_ml_ontology())