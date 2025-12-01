from google import genai

client = genai.Client(api_key='AIzaSyCorUATvMRJ7VO0aFWJeRj8Jjyk8wqt_Fw')

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain how AI works in a few words",
)

print(response.text)