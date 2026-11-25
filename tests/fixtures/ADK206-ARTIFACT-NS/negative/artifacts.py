from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService

a = GcsArtifactService(bucket_name="b")
b = InMemoryArtifactService()
