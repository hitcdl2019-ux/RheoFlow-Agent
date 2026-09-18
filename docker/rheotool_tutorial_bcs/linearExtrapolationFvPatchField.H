#ifndef linearExtrapolationFvPatchField_H
#define linearExtrapolationFvPatchField_H

#include "calculatedFvPatchField.H"

namespace Foam
{

template<class Type>
class linearExtrapolationFvPatchField
:
    public calculatedFvPatchField<Type>
{
public:

    TypeName("linearExtrapolation");

    linearExtrapolationFvPatchField
    (
        const fvPatch&,
        const DimensionedField<Type, volMesh>&
    );

    linearExtrapolationFvPatchField
    (
        const fvPatch&,
        const DimensionedField<Type, volMesh>&,
        const dictionary&
    );

    linearExtrapolationFvPatchField
    (
        const linearExtrapolationFvPatchField<Type>&,
        const fvPatch&,
        const DimensionedField<Type, volMesh>&,
        const fvPatchFieldMapper&
    );

    linearExtrapolationFvPatchField
    (
        const linearExtrapolationFvPatchField<Type>&
    ) = delete;

    linearExtrapolationFvPatchField
    (
        const linearExtrapolationFvPatchField<Type>&,
        const DimensionedField<Type, volMesh>&
    );

    virtual tmp<fvPatchField<Type>> clone
    (
        const DimensionedField<Type, volMesh>& iF
    ) const
    {
        return tmp<fvPatchField<Type>>
        (
            new linearExtrapolationFvPatchField<Type>(*this, iF)
        );
    }

    virtual void evaluate
    (
        const Pstream::commsTypes commsType=Pstream::commsTypes::blocking
    );
};

} // End namespace Foam

#ifdef NoRepository
    #include "linearExtrapolationFvPatchField.C"
#endif

#endif
