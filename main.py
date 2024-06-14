import replicate
import base64

# Ensure the path is correct and the file exists
file_path = r"C:\Users\Chiok\Desktop\low_res_addnoise.jpg"  # Adjust the file extension if necessary

with open(file_path, "rb") as file:
    input = {
        "img": file
    }
    output = replicate.run(
        "tencentarc/gfpgan:0fbacf7afc6c144e5be9767cff80f25aff23e52b0708f17e20f9879b2f21516c",
        input=input
    )
    print(output)