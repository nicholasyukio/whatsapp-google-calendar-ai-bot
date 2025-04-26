from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from twilio.twiml.messaging_response import MessagingResponse

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'POST':
        incoming_msg = request.POST.get('Body', '').strip().lower()
        response = MessagingResponse()

        if "agendar" in incoming_msg:
            reply = "Claro! Por favor, me diga o dia e a hora do compromisso."
        else:
            reply = "Olá! Digite 'agendar' para começar a marcar um compromisso."

        response.message(reply)
        return HttpResponse(str(response), content_type='text/xml')

    return HttpResponse("Método não permitido", status=405)
