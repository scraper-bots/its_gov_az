import pyttsx3
import PyPDF2

# Function to convert PDF to text
def pdf_to_text(file_path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfFileReader(file)
        text = ""
        for page in range(pdf_reader.numPages):
            page_obj = pdf_reader.getPage(page)
            text += page_obj.extractText()
    return text

# Function to convert text to speech
def text_to_speech(text):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Adjust the speech rate (default is 200)
    engine.setProperty('volume', 1)  # Adjust the speech volume (default is 1)
    engine.say(text)
    engine.runAndWait()

# Main script
if __name__ == '__main__':
    pdf_file = 'path/to/your/pdf_file.pdf'
    extracted_text = pdf_to_text(pdf_file)
    text_to_speech(extracted_text)
