def test_rtsp_module_import():
    import importlib
    m = importlib.import_module("src.roboflow_counter.stream.rtsp")
    assert hasattr(m, "run_rtsp_loop")
