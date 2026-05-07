from django.shortcuts import render,redirect,HttpResponse
from slmsapp.EmailBackEnd import EmailBackEnd
from django.contrib.auth import  logout,login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from slmsapp.models import CustomUser,Staff,Staff_Leave,LeaveType
from django.db.models import Q
from datetime import datetime, date, timedelta


MONTHLY_LEAVE_LIMIT = 3
STATUS_PENDING = 0
STATUS_APPROVED = 1
STATUS_REJECTED = 2
STATUS_CANCELLED = 3


def _parse_leave_date(date_string):
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _month_range(input_date):
    month_start = input_date.replace(day=1)
    if input_date.month == 12:
        next_month_start = date(input_date.year + 1, 1, 1)
    else:
        next_month_start = date(input_date.year, input_date.month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    return month_start, month_end


def _count_overlap_days(start_date, end_date, window_start, window_end):
    overlap_start = max(start_date, window_start)
    overlap_end = min(end_date, window_end)
    if overlap_start > overlap_end:
        return 0
    return (overlap_end - overlap_start).days + 1


def _approved_days_for_month(staff, month_date):
    month_start, month_end = _month_range(month_date)
    approved_leaves = Staff_Leave.objects.filter(staff_id=staff.id, status=STATUS_APPROVED)
    total_days = 0

    for leave in approved_leaves:
        leave_start = _parse_leave_date(leave.from_date)
        leave_end = _parse_leave_date(leave.to_date)
        if not leave_start or not leave_end or leave_end < leave_start:
            continue
        total_days += _count_overlap_days(leave_start, leave_end, month_start, month_end)

    return total_days


def _monthly_usage_by_request(request_start, request_end):
    usage = {}
    month_cursor = request_start.replace(day=1)
    last_month = request_end.replace(day=1)

    while month_cursor <= last_month:
        month_start, month_end = _month_range(month_cursor)
        key = month_cursor.strftime("%Y-%m")
        usage[key] = _count_overlap_days(request_start, request_end, month_start, month_end)

        if month_cursor.month == 12:
            month_cursor = date(month_cursor.year + 1, 1, 1)
        else:
            month_cursor = date(month_cursor.year, month_cursor.month + 1, 1)

    return usage




@login_required(login_url='/')
def HOME(request):
    staff = Staff.objects.get(admin=request.user.id)
    staff_leave_history = Staff_Leave.objects.filter(staff_id=staff.id).order_by('-created_at')

    monthly_limit = MONTHLY_LEAVE_LIMIT
    today = date.today()
    month_start, month_end = _month_range(today)
    total_taken_leaves = _approved_days_for_month(staff, today)
    # Count real requests created this month for accurate status cards.
    month_requests = Staff_Leave.objects.filter(
        staff_id=staff.id,
        created_at__year=today.year,
        created_at__month=today.month
    )
    pending_leaves = month_requests.filter(status=STATUS_PENDING).count()
    approved_leaves_count = month_requests.filter(status=STATUS_APPROVED).count()
    rejected_leaves_count = month_requests.filter(status=STATUS_REJECTED).count()

    remaining_leaves = monthly_limit - total_taken_leaves
    if remaining_leaves < 0:
        remaining_leaves = 0

    context = {
        'staff_leave_history': staff_leave_history,
        'monthly_limit': monthly_limit,
        'total_taken_leaves': total_taken_leaves,
        'remaining_leaves': remaining_leaves,
        'pending_leaves': pending_leaves,
        'approved_leaves_count': approved_leaves_count,
        'rejected_leaves_count': rejected_leaves_count,
        'current_month': month_start.strftime("%B %Y"),
    }
    return render(request,'staff/home.html',context)

@login_required(login_url='/')   
def STAFF_APPLY_LEAVE(request):
    staff = Staff.objects.get(admin=request.user.id)
    remaining_leaves = max(0, MONTHLY_LEAVE_LIMIT - _approved_days_for_month(staff, date.today()))
    leave_types = LeaveType.objects.filter(is_active=True).order_by('name')
    context = {
        'monthly_limit': MONTHLY_LEAVE_LIMIT,
        'remaining_leaves': remaining_leaves,
        'limit_message': f'You can take only {MONTHLY_LEAVE_LIMIT} days leave per month',
        'remaining_message': f'You have {remaining_leaves} days remaining this month',
        'today_date': date.today().strftime("%Y-%m-%d"),
        'leave_types': leave_types,
    }
    return render(request,'staff/apply_leave.html', context)


@login_required(login_url='/')   
def STAFF_APPLY_LEAVE_SAVE(request):
    if request.method == "POST":
        leave_type = (request.POST.get('leave_type') or '').strip()
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        duration_days = request.POST.get('duration_days')
        message = (request.POST.get('message') or '').strip()

        if not leave_type:
            messages.error(request, 'Please select a leave type.')
            return redirect('staff_apply_leave')

        leave_type_exists = LeaveType.objects.filter(name=leave_type, is_active=True).exists()
        if not leave_type_exists:
            messages.error(request, 'Selected leave type is not available.')
            return redirect('staff_apply_leave')

        staff = Staff.objects.get(admin=request.user.id)
        start_date = _parse_leave_date(from_date)
        end_date = _parse_leave_date(to_date)
        today = date.today()

        if not start_date or not end_date:
            messages.error(request, 'Please select valid leave dates.')
            return redirect('staff_apply_leave')

        if start_date < today or end_date < today:
            messages.error(request, 'Past dates are not allowed for leave request.')
            return redirect('staff_apply_leave')

        if end_date < start_date:
            messages.error(request, 'To Date must be greater than or equal to From Date.')
            return redirect('staff_apply_leave')

        if not duration_days:
            messages.error(request, 'Leave Duration is required.')
            return redirect('staff_apply_leave')

        try:
            duration_days = int(duration_days)
        except (TypeError, ValueError):
            messages.error(request, 'Leave Duration must be a valid number.')
            return redirect('staff_apply_leave')

        if duration_days <= 0:
            messages.error(request, 'Leave Duration must be greater than 0.')
            return redirect('staff_apply_leave')

        expected_duration = (end_date - start_date).days + 1
        if duration_days != expected_duration:
            messages.error(request, f'Leave Duration should be {expected_duration} day(s) for selected dates.')
            return redirect('staff_apply_leave')

        overlap_exists = Staff_Leave.objects.filter(staff_id=staff.id).exclude(status__in=[STATUS_REJECTED, STATUS_CANCELLED])
        for existing in overlap_exists:
            existing_start = _parse_leave_date(existing.from_date)
            existing_end = _parse_leave_date(existing.to_date)
            if not existing_start or not existing_end:
                continue
            if start_date <= existing_end and end_date >= existing_start:
                messages.error(request, 'This leave request overlaps with an existing pending/approved leave.')
                return redirect('staff_apply_leave')

        request_month_usage = _monthly_usage_by_request(start_date, end_date)
        for month_key, requested_days in request_month_usage.items():
            month_date = datetime.strptime(month_key + "-01", "%Y-%m-%d").date()
            approved_days = _approved_days_for_month(staff, month_date)
            if approved_days + requested_days > MONTHLY_LEAVE_LIMIT:
                month_remaining = max(0, MONTHLY_LEAVE_LIMIT - approved_days)
                messages.error(
                    request,
                    f'You can take only {MONTHLY_LEAVE_LIMIT} days leave per month. '
                    f'You have {month_remaining} days remaining this month.'
                )
                return redirect('staff_apply_leave')

        leave = Staff_Leave(
            staff_id = staff,
            leave_type = leave_type,
            from_date = from_date,
            to_date = to_date,
            duration_days=duration_days,
            message = message,
            status=STATUS_PENDING,
            reject_reason=None,
          )
        leave.save()
        messages.success(request,'Leave apply successfully')
        return redirect('staff_apply_leave')
    return redirect('staff_apply_leave')

@login_required(login_url='/')    
def STAFF_LEAVE_VIEW(request):
    staff = Staff.objects.get(admin=request.user.id)
    status_filter = request.GET.get('status', 'all')
    history_qs = Staff_Leave.objects.filter(staff_id=staff.id).order_by('-created_at')

    status_map = {
        'pending': STATUS_PENDING,
        'approved': STATUS_APPROVED,
        'rejected': STATUS_REJECTED,
        'cancelled': STATUS_CANCELLED,
    }
    if status_filter in status_map:
        history_qs = history_qs.filter(status=status_map[status_filter])
    else:
        status_filter = 'all'

    leave_records = []
    for leave in history_qs:
        start_date = _parse_leave_date(leave.from_date)
        end_date = _parse_leave_date(leave.to_date)
        duration_days = 0
        if start_date and end_date and end_date >= start_date:
            duration_days = (end_date - start_date).days + 1
        if leave.status == STATUS_PENDING:
            status_label = 'Pending'
            status_class = 'status-pending'
            tracking_state = 'pending'
        elif leave.status == STATUS_APPROVED:
            status_label = 'Approved'
            status_class = 'status-approved'
            tracking_state = 'approved'
        elif leave.status == STATUS_REJECTED:
            status_label = 'Rejected'
            status_class = 'status-rejected'
            tracking_state = 'rejected'
        else:
            status_label = 'Cancelled by Staff'
            status_class = 'status-cancelled'
            tracking_state = 'cancelled'

        leave_records.append({
            'leave': leave,
            'duration_days': duration_days,
            'status_label': status_label,
            'status_class': status_class,
            'tracking_state': tracking_state,
            'can_cancel': leave.status == STATUS_PENDING,
        })

    context = {
        'leave_records': leave_records,
        'status_filter': status_filter,
    }
    return render(request,'staff/leave_history.html',context)


@login_required(login_url='/')
def STAFF_CANCEL_LEAVE(request, id):
    if request.method != "POST":
        messages.error(request, 'Invalid request method.')
        return redirect('staff_leave_view')

    staff = Staff.objects.get(admin=request.user.id)
    leave = Staff_Leave.objects.filter(id=id, staff_id=staff.id).first()

    if not leave:
        messages.error(request, 'Leave request not found.')
        return redirect('staff_leave_view')

    if leave.status != STATUS_PENDING:
        messages.error(request, 'Only pending leave requests can be cancelled.')
        return redirect('staff_leave_view')

    leave.status = STATUS_CANCELLED
    leave.reject_reason = None
    leave.save()
    messages.success(request, 'Leave request cancelled successfully.')
    return redirect('staff_leave_view')
