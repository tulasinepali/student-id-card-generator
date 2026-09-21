from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.students.models import Student, VerificationRecord
from apps.academic.models import ClassLevel, Section, AcademicYear
from django.utils import timezone
from apps.idcards.models import IDCard
from apps.core.models import School

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone')


class TeacherProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    assigned_class_name = serializers.CharField(source='assigned_class.name', read_only=True, default='')
    assigned_section_name = serializers.CharField(source='assigned_section.name', read_only=True, default='')
    client_name = serializers.CharField(source='client.name', read_only=True, default=None)

    class Meta:
        model = TeacherProfile
        fields = (
            'id', 'employee_id', 'user', 'assigned_class', 'assigned_class_name',
            'assigned_section', 'assigned_section_name', 'client', 'client_name',
            'status', 'profile_photo'
        )


class StudentListSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    has_photo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = (
            'id', 'student_id', 'roll_number', 'full_name', 'gender',
            'class_level', 'class_name', 'section', 'section_name',
            'photo', 'has_photo', 'verification_status', 'status'
        )


class StudentDetailSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    has_photo = serializers.BooleanField(read_only=True)
    is_print_eligible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = (
            'id', 'student_id', 'roll_number', 'full_name', 'gender', 'date_of_birth',
            'class_level', 'class_name', 'section', 'section_name',
            'academic_year', 'academic_year_name',
            'address', 'guardian_name', 'guardian_phone', 'blood_group', 'emergency_contact',
            'photo', 'has_photo', 'verification_status', 'rejection_reason',
            'submitted_at', 'verified_at', 'status', 'is_print_eligible',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'student_id', 'roll_number', 'class_level', 'section', 'academic_year',
            'verification_status', 'rejection_reason', 'submitted_at', 'verified_at',
            'status', 'created_at', 'updated_at'
        )


class ClassSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ('id', 'name', 'class_level')


class ClassLevelWithSectionsSerializer(serializers.ModelSerializer):
    sections = ClassSectionSerializer(many=True, read_only=True)

    class Meta:
        model = ClassLevel
        fields = ('id', 'name', 'numeric_order', 'sections')


class StudentPermittedUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer allowing teachers to edit student ID, class, section,
    roll number, full name, date of birth, gender, guardian info,
    address, blood group, emergency contact.
    """
    class Meta:
        model = Student
        fields = (
            'student_id', 'class_level', 'section', 'roll_number', 'full_name',
            'date_of_birth', 'gender', 'address', 'guardian_name', 'guardian_phone',
            'blood_group', 'emergency_contact'
        )
        extra_kwargs = {
            'student_id': {'required': False},
            'class_level': {'required': False},
            'section': {'required': False},
            'roll_number': {'required': False},
            'full_name': {'required': False},
        }

    def validate_student_id(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Student ID cannot be empty.")
        if self.instance and Student.objects.filter(student_id=val).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(f"Student ID '{val}' is already in use by another student.")
        return val

    def validate(self, attrs):
        instance = self.instance
        class_level = attrs.get('class_level', instance.class_level if instance else None)
        section = attrs.get('section', instance.section if instance else None)
        roll = attrs.get('roll_number', instance.roll_number if instance else None)
        academic_year = instance.academic_year if instance else None

        if section and class_level and section.class_level_id != class_level.id:
            attrs['class_level'] = section.class_level

        if roll is not None and section is not None:
            effective_class = attrs.get('class_level') or (instance.class_level if instance else section.class_level)
            qs = Student.objects.filter(
                class_level=effective_class,
                section=section,
                academic_year=academic_year,
                roll_number=roll
            )
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"roll_number": f"Roll Number #{roll} is already assigned in this section."})

        return attrs


class TeacherStudentCreateSerializer(serializers.ModelSerializer):
    """
    Allows a class teacher to enroll a new student directly into their assigned class and section.
    Automatically scopes the student to the teacher's class, section, and the active academic year.
    """
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    has_photo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = (
            'id', 'student_id', 'roll_number', 'full_name', 'date_of_birth', 'gender',
            'blood_group', 'guardian_name', 'guardian_phone', 'address', 'emergency_contact',
            'class_name', 'section_name', 'has_photo', 'verification_status'
        )
        read_only_fields = ('id', 'class_name', 'section_name', 'has_photo', 'verification_status')
        extra_kwargs = {
            'student_id': {'required': False},
            'roll_number': {'required': True},
            'full_name': {'required': True},
        }

    def validate(self, attrs):
        request = self.context.get('request')
        profile = getattr(request.user, 'teacher_profile', None)
        if not profile or not profile.assigned_class or not profile.assigned_section:
            raise serializers.ValidationError("You do not have an active assigned class or section.")

        org = getattr(request.user, 'organization', None)
        active_year_qs = AcademicYear.objects.filter(is_active=True)
        if org:
            active_year = active_year_qs.filter(organization=org).first() or active_year_qs.filter(organization__isnull=True).first()
        else:
            active_year = active_year_qs.first()

        if not active_year:
            active_year = AcademicYear.objects.first()

        if not active_year:
            raise serializers.ValidationError("No academic year is defined in the system.")

        roll = attrs.get('roll_number')
        roll_check = Student.objects.filter(
            class_level=profile.assigned_class,
            section=profile.assigned_section,
            academic_year=active_year,
            roll_number=roll
        )
        if org:
            roll_check = roll_check.filter(organization=org)
        if getattr(profile, 'client_id', None):
            roll_check = roll_check.filter(client_id=profile.client_id)

        if roll_check.exists():
            raise serializers.ValidationError({"roll_number": f"Roll Number #{roll} is already in use in this section."})

        # Auto-generate student_id if not provided
        if not attrs.get('student_id'):
            last_stu = Student.objects.order_by('-id').first()
            next_num = (last_stu.id + 1) if last_stu else 1
            generated_id = f"STU{8000 + next_num}"
            while Student.objects.filter(student_id=generated_id).exists():
                next_num += 1
                generated_id = f"STU{8000 + next_num}"
            attrs['student_id'] = generated_id

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        profile = request.user.teacher_profile
        org = getattr(request.user, 'organization', None)
        client = getattr(profile, 'client', None)

        active_year_qs = AcademicYear.objects.filter(is_active=True)
        if org:
            active_year = active_year_qs.filter(organization=org).first() or active_year_qs.filter(organization__isnull=True).first()
        else:
            active_year = active_year_qs.first()

        if not active_year:
            active_year = AcademicYear.objects.first()

        student = Student.objects.create(
            organization=org,
            client=client,
            class_level=profile.assigned_class,
            section=profile.assigned_section,
            academic_year=active_year,
            submitted_by=request.user,
            submitted_at=timezone.now(),
            verification_status='PENDING',
            status='ACTIVE',
            **validated_data
        )
        return student


class QRVerificationResultSerializer(serializers.Serializer):
    status = serializers.CharField()  # ACTIVE, EXPIRED, REVOKED, INVALID
    status_display = serializers.CharField()
    message = serializers.CharField()
    student_id = serializers.CharField(required=False)
    student_name = serializers.CharField(required=False)
    class_name = serializers.CharField(required=False)
    section_name = serializers.CharField(required=False)
    photo_url = serializers.CharField(required=False, allow_null=True)
    school_name = serializers.CharField(required=False)
    valid_until = serializers.CharField(required=False)
    card_number = serializers.CharField(required=False)
