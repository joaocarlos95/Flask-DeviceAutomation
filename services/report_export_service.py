from datetime import datetime
from pathlib import Path
import pandas as pd
from classes.colors import Colors


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def export_parsed_excel(root_directory: str, parsed_data: dict, progress_callback=None) -> None:
    """
    Export parsed output as one XLSX per config_info, with one tab per command.
    """
    for config_info, command_map in parsed_data.items():
        path = Path(root_directory) / "outputfiles" / "GetConfigs" / config_info / _today()
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / f"[{_timestamp()}] {config_info}.xlsx"
        if progress_callback:
            progress_callback({
                "device": "-",
                "ip": "-",
                "config_info": config_info,
                "command": "excel_export",
                "status": "running",
                "message": f"Writing Excel file: {file_path.name}",
                "file_path": str(file_path),
            })
        print(
            f"{Colors.OK_GREEN}[>]{Colors.END} Saving data to excel\n"
            f"    Path: {path}\n"
            f"    Filename: {file_path.name}"
        )

        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            for command_name, rows in command_map.items():
                safe_sheet = str(command_name)[:31] or "sheet1"
                dataframe = pd.DataFrame(rows if rows else [])
                dataframe.to_excel(writer, sheet_name=safe_sheet, index=False)
        if progress_callback:
            progress_callback({
                "device": "-",
                "ip": "-",
                "config_info": config_info,
                "command": "excel_export",
                "status": "success",
                "message": f"Excel saved: {file_path.name}",
                "file_path": str(file_path),
            })
