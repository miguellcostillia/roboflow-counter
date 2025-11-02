from pydantic import BaseModel, Field

class InputCfg(BaseModel):
    rtsp_url: str = Field(..., description="RTSP(S) Kamera/Stream URL")

class OutputCfg(BaseModel):
    rtsp_url: str = Field(..., description="RTSP Ziel für MediaMTX/Relay")

class ModelCfg(BaseModel):
    id: str = Field(..., description="Roboflow model id (workspace/project:version)")

class AppCfg(BaseModel):
    name: str = "roboflow-counter"
    data_dir: str = "/opt/larvacounter/export"

class SecretsCfg(BaseModel):
    roboflow_api_key: str

class Config(BaseModel):
    app: AppCfg
    input: InputCfg
    output: OutputCfg
    model: ModelCfg
    secrets: SecretsCfg
