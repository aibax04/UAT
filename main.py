from workflows.graph import workflow
import os

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    
    print("="*60)
    print("UX/QA AUTOMATION AGENT")
    print("Testing: NexusAI Platform")
    print("="*60)
    
    # Test NexusAI with login credentials
    result = workflow.invoke({
        "app_name": "nexusai",
        "start_url": "https://nexusai-ndus.onrender.com/login?next=%2F"
    })
    
    print("\n" + "="*60)
    print("UX/QA ANALYSIS COMPLETE")
    print("="*60)
    print("\n" + result.get("report", "No report generated"))
    print("\n" + "="*60)
    print("Check the 'reports' folder for detailed analysis")
    print("Check the 'screenshots' folder for visual evidence")
    print("="*60)