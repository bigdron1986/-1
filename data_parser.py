# data_parser.py
import pandas as pd
import re
from io import StringIO
import os
from datetime import datetime

def parse_thermometry_file(file_path):
    """
    Parses a thermometry file (CSV or Excel) and extracts temperature data.

    Args:
        file_path (str): The path to the file (.csv or .xlsx).

    Returns:
        tuple: A tuple containing:
            - date (str): The date of the report in YYYY-MM-DD format.
            - data (list): A list of dictionaries, where each dictionary
                           represents a sensor reading.
    """
    try:
        # Extract date from filename
        filename = os.path.basename(file_path)
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', filename)
        if not date_match:
            raise ValueError("Date not found in filename")

        # Convert date to YYYY-MM-DD
        report_date_obj = datetime.strptime(date_match.group(1), '%d.%m.%Y')
        report_date = report_date_obj.strftime('%Y-%m-%d')

        # Determine file type and read accordingly
        if file_path.lower().endswith('.csv'):
            with open(file_path, 'r', encoding='windows-1251') as f:
                content = f.read()
            df = pd.read_csv(
                StringIO(content),
                delimiter=';',
                decimal=',',
                header=None,
                skip_blank_lines=True
            )
        elif file_path.lower().endswith('.xlsx'):
            # Read Excel file
            df = pd.read_excel(
                file_path,
                header=None
            )
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        parsed_data = []
        current_silo = None

        for index, row in df.iterrows():
            # Ищем название силоса: "Силос 3а", "Силос 4б" и т.д.
            # Проверяем ячейки 0 и 1, так как формат может отличаться
            cell_value = str(row[0]) + ' ' + str(row[1]) if pd.notna(row[0]) else str(row[1])
            
            silo_match = re.search(r'[Сс]илос\s+([0-9]+[а-яА-Я]?)', cell_value)
            if silo_match:
                current_silo = silo_match.group(1)
                continue

            # Ищем подвеску: "подвеска 1", "Подвеска 2" и т.д.
            suspension_match = re.search(r'[Пп]одвеска\s*(\d+)', str(row[1]), re.IGNORECASE)
            if suspension_match and current_silo:
                suspension_id = int(suspension_match.group(1))

                for i in range(2, 8):
                    if pd.notna(row[i]) and str(row[i]).strip():
                        try:
                            sensor_id = i - 1
                            # Заменяем запятую на точку для float
                            temp_str = str(row[i]).replace(',', '.')
                            temperature = float(temp_str)
                            parsed_data.append({
                                'silo': current_silo,
                                'suspension': suspension_id,
                                'sensor': sensor_id,
                                'temperature': temperature,
                                'date': report_date
                            })
                        except (ValueError, TypeError):
                            # Ignore cells that cannot be converted to float
                            continue
        return report_date, parsed_data

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None, []
    except Exception as e:
        print(f"An error occurred during parsing: {e}")
        return None, []

if __name__ == '__main__':
    # Example usage:
    # Create a dummy file for testing
    dummy_file_path = 'termo_05.03.2026.csv'
    
    # Run the parser
    date, data = parse_thermometry_file(dummy_file_path)

    if date and data:
        print(f"Report Date: {date}")
        print(f"Successfully parsed {len(data)} sensor readings.")
        # Print the first 5 readings for verification
        for item in data[:5]:
            print(item)
        
        # Print a reading with error value 71.2 if it exists
        error_reading = next((item for item in data if item['temperature'] == 71.2), None)
        if error_reading:
            print("\nFound a sensor error reading:")
            print(error_reading)
