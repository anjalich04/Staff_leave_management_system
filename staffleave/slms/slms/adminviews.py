
from django.shortcuts import render,redirect,HttpResponse
from slmsapp.EmailBackEnd import EmailBackEnd
from django.contrib.auth import  logout,login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from slmsapp.models import CustomUser,Staff,Staff_Leave,LeaveType
from django.db.models import Q

@login_required(login_url='/')
def HOME(request):
    staff_count = Staff.objects.count()
    leave_qs = Staff_Leave.objects.all()
    leave_count = leave_qs.count()
    pending_count = leave_qs.filter(status=0).count()
    approved_count = leave_qs.filter(status=1).count()
    rejected_count = leave_qs.filter(status=2).count()
    context = {
        'staff_count': staff_count,
        'leave_count': leave_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request,'admin/home.html',context)


def ADD_STAFF(request):
    if request.method == "POST":
        profile_pic = request.FILES.get('profile_pic')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        address = request.POST.get('address')
        gender = request.POST.get('gender')

        if CustomUser.objects.filter(email=email).exists():
            messages.warning(request,'Email is already Exist')
            return redirect('add_staff')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.warning(request,'Username is already Exist')
            return redirect('add_staff')
        
        else:
            user = CustomUser(first_name = first_name,last_name = last_name,email = email, profile_pic = profile_pic, user_type = 2, username = username)
            user.set_password(password)
            user.save()
            staff = Staff(
                admin = user,
                address = address,
                gender = gender
            )
            staff.save()
            messages.success(request,'Staff details has beend added successfully')
            return redirect('add_staff')

    return render(request,'admin/add_staff.html')

def VIEW_STAFF(request):
    staff = Staff.objects.select_related('admin').all().order_by('-created_at')
    context = {
        "staff":staff,
    }
    return render(request,'admin/view_staff.html',context)

def EDIT_STAFF(request,id):
    staff = Staff.objects.get(id = id)
    context = {
        "staff":staff,
    }
    return render(request,'admin/edit_staff.html',context)

def UPDATE_STAFF(request):
    if request.method == "POST":
        staff_id = request.POST.get('staff_id')
        profile_pic = request.FILES.get('profile_pic')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        address = request.POST.get('address')
        gender = request.POST.get('gender')

        user = CustomUser.objects.get(id = staff_id)
        user.username =username
        user.first_name =first_name
        user.last_name =last_name
        user.email =email

        if password != None and password !="":
            user.set_password(password)
        if profile_pic != None and profile_pic !="":
            user.profile_pic = profile_pic
        user.save()
        staff = Staff.objects.get(admin = staff_id)
        staff.gender = gender
        staff.address = address
        staff.save()
        messages.success(request,'Staf details has been succeesfully updated')
        return redirect('view_staff')
        
    return render(request,'admin/edit_staff.html')

def DELETE_STAFF(request,admin):
    staff = CustomUser.objects.get(id = admin)
    staff.delete()
    messages.success(request,"Staff record has been deleted successfully.")
    return redirect('view_staff')


def STAFF_LEAVE_VIEW(request):
    staff_leave = Staff_Leave.objects.select_related('staff_id__admin').all().order_by('-created_at')
    context = {
        "staff_leave":staff_leave,
    }
    
    return render(request,'admin/staff_leave.html',context)

def STAFF_APPROVE_LEAVE(request,id):
    leave = Staff_Leave.objects.get(id = id)
    leave.status = 1
    leave.save()
    return redirect('staff_leave_view_admin')

def STAFF_DISAPPROVE_LEAVE(request,id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect('staff_leave_view_admin')

    reject_reason = request.POST.get('reject_reason', '').strip()
    if not reject_reason:
        messages.error(request, "Rejection reason is required.")
        return redirect('staff_leave_view_admin')

    leave = Staff_Leave.objects.get(id = id)
    leave.status = 2
    leave.reject_reason = reject_reason
    leave.save()
    messages.success(request, "Leave request rejected with reason.")
    return redirect('staff_leave_view_admin')


@login_required(login_url='/')
def LEAVE_TYPE_LIST(request):
    leave_types = LeaveType.objects.all().order_by('-created_at')
    context = {
        "leave_types": leave_types,
    }
    return render(request, 'admin/leave_type_list.html', context)


@login_required(login_url='/')
def LEAVE_TYPE_ADD(request):
    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Leave type name is required.')
            return redirect('leave_type_add')

        if LeaveType.objects.filter(name__iexact=name).exists():
            messages.error(request, 'Leave type already exists.')
            return redirect('leave_type_add')

        LeaveType.objects.create(
            name=name,
            description=description,
            is_active=is_active
        )
        messages.success(request, 'Leave type added successfully.')
        return redirect('leave_type_list')
    return render(request, 'admin/leave_type_form.html')


@login_required(login_url='/')
def LEAVE_TYPE_EDIT(request, id):
    leave_type = LeaveType.objects.get(id=id)
    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Leave type name is required.')
            return redirect('leave_type_edit', id=id)

        if LeaveType.objects.filter(name__iexact=name).exclude(id=id).exists():
            messages.error(request, 'Leave type already exists.')
            return redirect('leave_type_edit', id=id)

        leave_type.name = name
        leave_type.description = description
        leave_type.is_active = is_active
        leave_type.save()
        messages.success(request, 'Leave type updated successfully.')
        return redirect('leave_type_list')

    context = {
        "leave_type": leave_type,
    }
    return render(request, 'admin/leave_type_form.html', context)


@login_required(login_url='/')
def LEAVE_TYPE_DELETE(request, id):
    if request.method != "POST":
        messages.error(request, 'Invalid request method for delete.')
        return redirect('leave_type_list')

    leave_type = LeaveType.objects.get(id=id)
    leave_type.delete()
    messages.success(request, 'Leave type deleted successfully.')
    return redirect('leave_type_list')



