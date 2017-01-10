__author__ = 'Azharul'

from django.shortcuts import render

def home(request):
    response = render(request, 'home.html', {'user': request.user})  # django.http.HttpResponse
    return response

#def login(request):
#    request_context = {}
#    if request.POST:
#        username = request.data.get('username', '')
#        password = request.data.get('password', '')
#
#        try:
#            user = UserResource().authenticate(username, password)
#            request.session['user_id'] = user.id
#            return HttpResponseRedirect('/')
#        except UserDoesNotExistError, e:
#            request_context.update({'error': True, 'success': False,  'message': e})
#
#    return render(request, 'login.html', request_context)
#
#def logout(request):
#    request.session.flush()
#    request.session['user_id'] = None
#    return HttpResponseRedirect('/login/')