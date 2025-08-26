import requests

# server configuration
server_ip = "localhost"
server_port = 8080
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
        params = {"time_lower": 1756047158187, "time_upper": 1756047178323}
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