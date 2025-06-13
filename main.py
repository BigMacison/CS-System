from libraries.ResticInterface import ResticInterface
import asyncio

async def printing(line):
  print(f"[LINE] {line}")

async def main():
  chosen_endpoint = ""
  password = ""

  while True:
    print("Choose endpoint:")
    endpoints = ResticInterface.getEndpointsFromConfig()
    for index, value in enumerate(endpoints):
      print(f"({index}) {value}")
    chosen_endpoint = endpoints[int(input("> "))]
      
    if not ResticInterface(chosen_endpoint, "").isRepo("/cssystem/Server1"):
      print("This endpoint has no configured servers. Do you want to make one? (Y/n)")
      if input("> ").capitalize() == "Y":
        print("Choose a password for the Server:")
        password = input("> ")
        ResticInterface(chosen_endpoint, password).initRepo("/cssystem/Server1")
        
    else:
      password = input("password > ")
      break

  resticInterface = ResticInterface(chosen_endpoint, password)
  print(resticInterface.getSnapshots("/cssystem/Server1"))
  print("yay")
  while True:
    await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(main())