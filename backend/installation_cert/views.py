import io
import re
from datetime import date

from django.db import transaction

from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # noqa: F401 — TA_CENTER used in table ALIGN

from works.models import Work, WorkItem, WorkItemEntry
from works.utils import is_assigned_consignee
from .models import GeneratedCertificate


EXCLUDED_CATEGORIES = {WorkItem.CATEGORY_SUPPLY}


def _is_admin(user):
    if user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'admin'


def _all_works():
    """All works — any consignee can generate a certificate for any LOA."""
    return Work.objects.all()


def _work_fy(work) -> str:
    """Financial year derived from the work's own date."""
    from datetime import datetime
    raw = work.date
    if not raw:
        d = date.today()
    elif isinstance(raw, str):
        s = raw.strip()
        if s.isdigit():
            # Excel serial date — days since 1899-12-30
            from datetime import timedelta
            d = date(1899, 12, 30) + timedelta(days=int(s))
        else:
            d = datetime.strptime(s[:10], '%Y-%m-%d').date()
    else:
        d = raw if isinstance(raw, date) else raw.date()
    y = d.year if d.month >= 4 else d.year - 1
    return f"{str(y)[2:]}-{str(y + 1)[2:]}"


def _auto_cert_number(work, cert_seq=None):
    """Suggest cert number: {prefix} {work_seq:02d} of {fy}/{cert_seq:03d}"""
    # tender_number usually has readable alpha prefix (e.g. "Tele 02 of 25-26")
    for raw in (work.tender_number, work.loa_number):
        if raw:
            m = re.match(r'^([A-Za-z]+)', raw.strip())
            if m:
                prefix = m.group(1)[:6].title()
                break
    else:
        prefix = 'Cert'

    work_seq = Work.objects.filter(pk__lte=work.pk).count()

    if cert_seq is None:
        cert_seq = GeneratedCertificate.objects.filter(work=work).count() + 1
    fy = _work_fy(work)
    return f"{prefix} {work_seq:02d} of {fy}/{cert_seq:03d}"


class LOAListView(APIView):
    """GET /api/installation-cert/loas/ — all works."""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        works = _all_works().values(
            'id', 'loa_number', 'tender_number',
            'contractor_name', 'name_of_work', 'date',
        )
        result = []
        for w in works:
            result.append({
                'id': w['id'],
                'loa_number': w['loa_number'] or '—',
                'loa_date': w['date'] or '',
                'tender_number': w['tender_number'] or '—',
                'contractor_name': w['contractor_name'] or '—',
                'name_of_work': w['name_of_work'] or '—',
            })
        return Response(result)


class LOAItemsView(APIView):
    """GET /api/installation-cert/items/?loa_id=X"""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        loa_id = request.query_params.get('loa_id')
        if not loa_id:
            return Response({'error': 'loa_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        items = (
            WorkItem.objects
            .filter(work_id=loa_id)
            .exclude(category__in=list(EXCLUDED_CATEGORIES))
            .values('id', 'schedule', 'serial_number', 'item_desc', 'unit', 'category')
        )
        return Response(list(items))


class EntriesPreviewView(APIView):
    """GET /api/installation-cert/entries/?loa_id=X[&item_id=Y][&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD]"""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        loa_id = request.query_params.get('loa_id')
        if not loa_id:
            return Response({'error': 'loa_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        item_id   = request.query_params.get('item_id')
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        qs = (
            WorkItemEntry.objects
            .filter(work_item__work_id=loa_id)
            .exclude(work_item__category__in=list(EXCLUDED_CATEGORIES))
            .select_related('work_item')
        )

        if not (_is_admin(request.user) or is_assigned_consignee(request.user, Work.objects.get(pk=loa_id))):
            qs = qs.filter(submitted_by=request.user)

        if item_id:
            qs = qs.filter(work_item_id=item_id)
        if date_from:
            try:
                qs = qs.filter(submitted_at__date__gte=date_from)
            except Exception:
                pass
        if date_to:
            try:
                qs = qs.filter(submitted_at__date__lte=date_to)
            except Exception:
                pass

        result = []
        for e in qs.order_by('work_item__schedule', 'work_item__serial_number', 'submitted_at'):
            result.append({
                'entry_id':      e.id,
                'item_id':       e.work_item_id,
                'schedule':      e.work_item.schedule or '',
                'serial_number': e.work_item.serial_number or '',
                'item_desc':     e.work_item.item_desc or '',
                'quantity':      e.quantity,
                'unit':          e.work_item.unit or '',
                'location':      e.location or '',
                'remarks':       e.remarks or '',
                'submitted_at':  e.submitted_at.date().isoformat(),
            })
        return Response(result)


class SuggestCertNumberView(APIView):
    """GET /api/installation-cert/suggest-number/?loa_id=X"""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        loa_id = request.query_params.get('loa_id')
        if not loa_id:
            return Response({'error': 'loa_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = _all_works().get(id=loa_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'cert_number': _auto_cert_number(work)})


class PreviewCertView(APIView):
    """POST /api/installation-cert/preview/
    Body: { loa_id, entry_ids: [...] }
    Returns PDF inline (no save).
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        loa_id    = request.data.get('loa_id')
        entry_ids = request.data.get('entry_ids', [])
        cert_number = request.data.get('cert_number', '')

        if not loa_id or not entry_ids:
            return Response({'error': 'loa_id and entry_ids required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = _all_works().get(id=loa_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        entries = (
            WorkItemEntry.objects
            .filter(id__in=entry_ids, work_item__work_id=loa_id)
            .exclude(work_item__category__in=list(EXCLUDED_CATEGORIES))
            .select_related('work_item')
            .order_by('work_item__schedule', 'work_item__serial_number', 'submitted_at')
        )

        if not entries.exists():
            return Response({'error': 'No eligible entries found.'}, status=status.HTTP_400_BAD_REQUEST)

        designation = ''
        try:
            designation = request.user.profile.designation or ''
        except Exception:
            pass

        pdf_bytes = _build_pdf(work, list(entries), designation, cert_number)
        buf = io.BytesIO(pdf_bytes)
        response = FileResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="preview.pdf"'
        return response


class GenerateCertView(APIView):
    """POST /api/installation-cert/generate/
    Body: { loa_id, entry_ids: [...], cert_number: '...' }
    Saves record + returns PDF as attachment.
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        loa_id      = request.data.get('loa_id')
        entry_ids   = request.data.get('entry_ids', [])
        cert_number = request.data.get('cert_number', '')

        if not loa_id or not entry_ids:
            return Response({'error': 'loa_id and entry_ids required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work = _all_works().get(id=loa_id)
        except Work.DoesNotExist:
            return Response({'error': 'Work not found.'}, status=status.HTTP_404_NOT_FOUND)

        entries = (
            WorkItemEntry.objects
            .filter(id__in=entry_ids, work_item__work_id=loa_id)
            .exclude(work_item__category__in=list(EXCLUDED_CATEGORIES))
            .select_related('work_item')
            .order_by('work_item__schedule', 'work_item__serial_number', 'submitted_at')
        )

        if not entries.exists():
            return Response({'error': 'No eligible entries found.'}, status=status.HTTP_400_BAD_REQUEST)

        designation = ''
        try:
            designation = request.user.profile.designation or ''
        except Exception:
            pass

        with transaction.atomic():
            # Lock all certs for this work to prevent seq race
            existing_certs = list(
                GeneratedCertificate.objects.select_for_update()
                .filter(work=work)
            )

            if not cert_number:
                cert_seq = len(existing_certs) + 1
                cert_number = _auto_cert_number(work, cert_seq=cert_seq)
            else:
                # Conflict check for manually entered cert number
                conflict = next(
                    (c for c in existing_certs if c.cert_number == cert_number),
                    None,
                )
                if conflict:
                    if conflict.user_id != request.user.id:
                        return Response(
                            {'error': 'cert_belongs_to_other',
                             'message': f'Certificate "{cert_number}" was generated by another user.'},
                            status=status.HTTP_409_CONFLICT,
                        )
                    # Same user — require explicit replace confirmation
                    replace_id = request.data.get('replace_cert_id')
                    if not replace_id:
                        return Response(
                            {'error': 'cert_exists_own',
                             'message': f'You already have certificate "{cert_number}". Replace it?',
                             'existing_cert_id': conflict.id},
                            status=status.HTTP_409_CONFLICT,
                        )
                    GeneratedCertificate.objects.filter(
                        id=replace_id, user=request.user
                    ).delete()

            GeneratedCertificate.objects.create(
                user=request.user,
                work=work,
                cert_number=cert_number,
                entry_ids=list(entry_ids),
                designation=designation,
            )

        pdf_bytes = _build_pdf(work, list(entries), designation, cert_number)
        buf = io.BytesIO(pdf_bytes)
        return FileResponse(
            buf,
            as_attachment=True,
            filename=f"installation_certificate_{cert_number.replace('/', '_')}.pdf",
            content_type='application/pdf',
        )


class CertificateListView(APIView):
    """GET /api/installation-cert/certificates/ — certs generated by current user."""
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        certs = GeneratedCertificate.objects.filter(user=request.user).select_related('work')
        result = []
        for c in certs:
            result.append({
                'id':           c.id,
                'cert_number':  c.cert_number,
                'loa_number':   c.work.loa_number or '—',
                'loa_id':       c.work_id,
                'contractor':   c.work.contractor_name or '—',
                'name_of_work': c.work.name_of_work or '—',
                'generated_at': c.generated_at.isoformat(),
                'entry_count':  len(c.entry_ids),
            })
        return Response(result)


class CertificateDetailView(APIView):
    """DELETE /api/installation-cert/certificates/<id>/"""
    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            cert = GeneratedCertificate.objects.get(id=pk, user=request.user)
        except GeneratedCertificate.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        cert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificatePDFView(APIView):
    """GET /api/installation-cert/certificates/<id>/pdf/ — re-download a saved cert."""
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            cert = GeneratedCertificate.objects.get(id=pk, user=request.user)
        except GeneratedCertificate.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        entries = (
            WorkItemEntry.objects
            .filter(id__in=cert.entry_ids, work_item__work_id=cert.work_id)
            .exclude(work_item__category__in=list(EXCLUDED_CATEGORIES))
            .select_related('work_item')
            .order_by('work_item__schedule', 'work_item__serial_number', 'submitted_at')
        )

        inline = request.query_params.get('inline') == '1'
        pdf_bytes = _build_pdf(cert.work, list(entries), cert.designation, cert.cert_number)
        buf = io.BytesIO(pdf_bytes)

        if inline:
            response = FileResponse(buf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="cert_{cert.id}.pdf"'
            return response

        return FileResponse(
            buf,
            as_attachment=True,
            filename=f"installation_certificate_{cert.cert_number.replace('/', '_')}.pdf",
            content_type='application/pdf',
        )


# ---------------------------------------------------------------------------
# PDF builder — A4 portrait
# ---------------------------------------------------------------------------

def _build_pdf(work: Work, entries: list, designation: str, cert_number: str = '') -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CertTitle',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=3,
        fontName='Helvetica-Bold',
    )
    certno_style = ParagraphStyle(
        'CertNo',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_RIGHT,
        spaceAfter=2,
    )
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=8,
        leading=12,
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=7,
        leading=10,
        wordWrap='CJK',
    )
    sig_left_style = ParagraphStyle(
        'SigLeft',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_LEFT,
        spaceBefore=0,
    )
    sig_right_style = ParagraphStyle(
        'SigRight',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_RIGHT,
        spaceBefore=0,
    )

    today = date.today().strftime('%d-%m-%Y')
    loa_date = work.date or ''

    story = []

    # Cert number + date (right-aligned)
    if cert_number:
        story.append(Paragraph(f'<b>Cert No.:</b> {cert_number} &nbsp;&nbsp; <b>Date:</b> {today}', certno_style))
    else:
        story.append(Paragraph(f'<b>Date:</b> {today}', certno_style))

    # Title
    story.append(Paragraph('INSTALLATION CERTIFICATE', title_style))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.black, spaceAfter=5))

    # Header info table
    page_w = A4[0] - 30 * mm  # ~180mm

    header_data = [
        [Paragraph('<b>LOA Number:</b>', label_style),
         Paragraph(work.loa_number or '—', label_style),
         Paragraph('<b>LOA Date:</b>', label_style),
         Paragraph(str(loa_date) if loa_date else '—', label_style)],
        [Paragraph('<b>Tender No.:</b>', label_style),
         Paragraph(work.tender_number or '—', label_style),
         Paragraph('<b>Contractor:</b>', label_style),
         Paragraph(work.contractor_name or '—', label_style)],
        [Paragraph('<b>Name of Work:</b>', label_style),
         Paragraph(work.name_of_work or '—', label_style),
         Paragraph('', label_style),
         Paragraph('', label_style)],
    ]

    col_w = page_w / 4
    header_table = Table(
        header_data,
        colWidths=[col_w * 0.65, col_w * 1.05, col_w * 0.65, col_w * 1.65],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('SPAN',          (1, 2), (3, 2)),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5 * mm))

    # Main data table — portrait column widths (total ~180mm)
    table_header = [
        Paragraph('<b>Sch</b>', cell_style),
        Paragraph('<b>S.No.</b>', cell_style),
        Paragraph('<b>Item Description</b>', cell_style),
        Paragraph('<b>Qty</b>', cell_style),
        Paragraph('<b>Unit</b>', cell_style),
        Paragraph('<b>Location</b>', cell_style),
        Paragraph('<b>Remark</b>', cell_style),
    ]

    rows = [table_header]
    for e in entries:
        qty_str = str(int(e.quantity)) if e.quantity == int(e.quantity) else str(e.quantity)
        rows.append([
            Paragraph(e.work_item.schedule or '', cell_style),
            Paragraph(e.work_item.serial_number or '', cell_style),
            Paragraph(e.work_item.item_desc or '', cell_style),
            Paragraph(qty_str, cell_style),
            Paragraph(e.work_item.unit or '', cell_style),
            Paragraph(e.location or '', cell_style),
            Paragraph(e.remarks or '', cell_style),
        ])

    col_widths = [
        12 * mm,   # Sch
        12 * mm,   # S.No.
        62 * mm,   # Item Description
        13 * mm,   # Qty
        14 * mm,   # Unit
        35 * mm,   # Location
        32 * mm,   # Remark
    ]  # total = 180mm

    data_table = Table(rows, colWidths=col_widths, repeatRows=1)
    data_table.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 7),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('ALIGN',         (3, 0), (4, -1), 'CENTER'),
    ]))
    story.append(data_table)

    # Signature footer — 2 blank lines gap, then two-column row
    story.append(Spacer(1, 14 * mm))
    sig_table = Table(
        [[Paragraph('Contractor Signature', sig_left_style),
          Paragraph(designation if designation else '', sig_right_style)]],
        colWidths=[page_w / 2, page_w / 2],
    )
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buf.getvalue()
