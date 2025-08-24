import requests

# server configuration
server_ip = "localhost"
server_port = 8080
url = f"http://{server_ip}:{server_port}/rover/arm/P_param"

while True:
    try:
        # Ask the user for input
        user_input = input("Enter a number (or 'q' to quit): ")
        if user_input.lower() == 'q':
            print("Exiting...")
            break

        # Convert input to a number
        value = float(user_input)

        # Send the GET request
        params = {"value": value}
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
