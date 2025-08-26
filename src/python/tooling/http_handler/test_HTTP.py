import requests
import time

# server configuration
server_ip = "localhost"
server_port = 9000
url = f"http://{server_ip}:{server_port}/rover/chassis/motor_driver/back_left_pivot/current"

while True:
    try:
        # # Ask the user for input
        # user_input = input("Enter a number (or 'q' to quit): ")
        # if user_input.lower() == 'q':
        #     print("Exiting...")
        #     break

        # Convert input to a number
        # value = float(user_input)

        # Send the GET request
        params = {"start": 1756180933783, "end": 1756180939261}
        response = requests.get(url, params=params)

        # Check if request was successful
        if response.status_code == 200:
            try:
                print("Response received:", response.json())
            except ValueError:
                print("Response received:", response.text)
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except ValueError:
        print("Invalid input. Please enter a number.")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

    time.sleep(1)  # wait for 1 second before next input